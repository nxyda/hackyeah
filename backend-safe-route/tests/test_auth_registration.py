"""Testy rejestracji kont lokalnych i pierwszego logowania OAuth."""

import asyncio
from types import SimpleNamespace

import pytest
import jwt
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError

from app import security
from app.enums.oauth_provider import OAuthProvider
from app.schemas.auth import RegisterRequest
from app.services import auth_service
from app.services.auth_service import (
    AuthService,
    DuplicateAccountError,
    InvalidCredentialsError,
)
from app.services.oauth_provider_service import OAuthProfile


class StubSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class StubUserRepository:
    def __init__(self, user: SimpleNamespace | None = None) -> None:
        self.session = StubSession()
        self.user = user
        self.next_id = 17
        self.users_by_email: dict[str, SimpleNamespace] = {}
        self.users_by_identity: dict[tuple[str, str], SimpleNamespace] = {}
        self.created_identities: list[tuple[int, str, str]] = []

    async def get_by_email(self, email: str) -> SimpleNamespace | None:
        return self.users_by_email.get(email) or self.user

    async def get_by_identity(
        self,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> SimpleNamespace | None:
        return self.users_by_identity.get((provider, provider_user_id))

    async def create(
        self,
        *,
        email: str,
        password_hash: str | None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> SimpleNamespace:
        user = SimpleNamespace(
            id=self.next_id,
            email=email,
            password_hash=password_hash,
            given_name=given_name,
            family_name=family_name,
            is_active=True,
        )
        self.next_id += 1
        self.users_by_email[email] = user
        return user

    async def create_identity(
        self,
        *,
        user_id: int,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> None:
        self.created_identities.append((user_id, provider, provider_user_id))
        self.users_by_identity[(provider, provider_user_id)] = next(
            user
            for user in self.users_by_email.values()
            if user.id == user_id
        )


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret_key=SimpleNamespace(
                get_secret_value=lambda: "registration-test-key-that-is-over-32-bytes"
            ),
            jwt_access_token_expire_minutes=15,
            jwt_issuer="registration-tests",
        ),
    )


def test_register_hashes_password_and_returns_profile(jwt_settings: None) -> None:
    repository = StubUserRepository()
    result = asyncio.run(
        AuthService(repository).register(
            RegisterRequest(
                email=" Person@Example.com ",
                password="very-secure-test-password",
                given_name="  Ada ",
                family_name=" Lovelace  ",
            )
        )
    )

    created = repository.users_by_email["person@example.com"]
    assert PasswordHash.recommended().verify(
        "very-secure-test-password",
        created.password_hash,
    )
    assert result.user.email == "person@example.com"
    assert result.user.given_name == "Ada"
    assert result.user.family_name == "Lovelace"
    assert repository.session.commits == 1


def test_register_rejects_existing_email() -> None:
    existing = SimpleNamespace(email="person@example.com")
    repository = StubUserRepository(existing)

    with pytest.raises(DuplicateAccountError):
        asyncio.run(
            AuthService(repository).register(
                RegisterRequest(
                    email="person@example.com",
                    password="very-secure-test-password",
                )
            )
        )


@pytest.mark.parametrize("email_conflict", [True, False])
def test_register_rolls_back_integrity_failure_and_only_maps_email_conflict(
    email_conflict: bool,
) -> None:
    existing = SimpleNamespace(email="person@example.com") if email_conflict else None

    class IntegrityErrorRepository(StubUserRepository):
        async def create(self, **kwargs) -> SimpleNamespace:
            if email_conflict:
                self.users_by_email[kwargs["email"]] = existing
            raise IntegrityError("INSERT", {}, Exception("constraint failure"))

    repository = IntegrityErrorRepository()
    details = RegisterRequest(
        email="person@example.com",
        password="a-valid-length-password",
    )

    expected_error = DuplicateAccountError if email_conflict else IntegrityError
    with pytest.raises(expected_error):
        asyncio.run(AuthService(repository).register(details))

    assert repository.session.rollbacks == 1
    assert repository.session.commits == 0


def test_oauth_creates_user_and_persists_provider_identity(
    jwt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = StubUserRepository()
    profile = OAuthProfile(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-subject-123",
        email="person@example.com",
        given_name="Ada",
        family_name="Lovelace",
    )
    monkeypatch.setattr(
        auth_service,
        "verify_oauth_credential",
        lambda provider, credential: _async_value(profile),
    )

    result = asyncio.run(
        AuthService(repository).login_with_oauth(
            OAuthProvider.GOOGLE,
            "verified-id-token",
        )
    )

    assert result.user.email == "person@example.com"
    assert result.user.given_name == "Ada"
    assert result.user.family_name == "Lovelace"
    assert repository.created_identities == [(17, "google", "google-subject-123")]
    assert repository.session.commits == 1


def test_oauth_rejects_inactive_linked_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inactive_user = SimpleNamespace(
        id=42,
        email="person@example.com",
        given_name="Ada",
        family_name=None,
        is_active=False,
    )
    repository = StubUserRepository()
    repository.users_by_identity[(OAuthProvider.GOOGLE, "google-subject-123")] = (
        inactive_user
    )
    profile = OAuthProfile(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-subject-123",
        email="person@example.com",
        given_name="Ada",
        family_name=None,
    )
    monkeypatch.setattr(
        auth_service,
        "verify_oauth_credential",
        lambda provider, credential: _async_value(profile),
    )

    with pytest.raises(InvalidCredentialsError):
        asyncio.run(
            AuthService(repository).login_with_oauth(
                OAuthProvider.GOOGLE,
                "verified-id-token",
            )
        )

    assert repository.session.commits == 0


def test_oauth_does_not_automatically_link_an_existing_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = StubUserRepository(SimpleNamespace(email="person@example.com"))
    profile = OAuthProfile(
        provider=OAuthProvider.FACEBOOK,
        provider_user_id="facebook-subject-456",
        email="person@example.com",
        given_name=None,
        family_name=None,
    )
    monkeypatch.setattr(
        auth_service,
        "verify_oauth_credential",
        lambda provider, credential: _async_value(profile),
    )

    with pytest.raises(DuplicateAccountError):
        asyncio.run(
            AuthService(repository).login_with_oauth(
                OAuthProvider.FACEBOOK,
                "access-token",
            )
        )


def test_oauth_identity_race_returns_token_for_the_existing_account(
    jwt_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    concurrent_user = SimpleNamespace(
        id=99,
        email="person@example.com",
        given_name="Ada",
        family_name=None,
        is_active=True,
    )

    class ConcurrentIdentityRepository(StubUserRepository):
        async def create_identity(
            self,
            *,
            user_id: int,
            provider: OAuthProvider,
            provider_user_id: str,
        ) -> None:
            self.users_by_identity[(provider, provider_user_id)] = concurrent_user
            raise IntegrityError("INSERT", {}, Exception("concurrent identity"))

    profile = OAuthProfile(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-subject-123",
        email="person@example.com",
        given_name="Ada",
        family_name=None,
    )
    monkeypatch.setattr(
        auth_service,
        "verify_oauth_credential",
        lambda provider, credential: _async_value(profile),
    )
    repository = ConcurrentIdentityRepository()

    result = asyncio.run(
        AuthService(repository).login_with_oauth(
            OAuthProvider.GOOGLE,
            "verified-id-token",
        )
    )
    claims = jwt.decode(
        result.access_token,
        "registration-test-key-that-is-over-32-bytes",
        algorithms=["HS256"],
        issuer="registration-tests",
    )

    assert claims["sub"] == "99"
    assert repository.session.rollbacks == 1


async def _async_value(value: OAuthProfile) -> OAuthProfile:
    return value
