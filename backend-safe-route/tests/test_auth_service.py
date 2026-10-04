"""Testy logowania użytkownika i wystawiania tokenów dostępu."""

import asyncio
from types import SimpleNamespace

import jwt
import pytest
from pydantic import SecretStr
from pwdlib import PasswordHash

from app.schemas.auth import LoginRequest
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
)
from app import security
from app.security import JWT_ALGORITHM

TEST_SECRET = "test-secret-key-that-is-at-least-32-bytes"


class StubUserRepository:
    def __init__(self, user: SimpleNamespace | None) -> None:
        self.user = user
        self.requested_email: str | None = None

    async def get_by_email(self, email: str) -> SimpleNamespace | None:
        self.requested_email = email
        return self.user


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret_key=SecretStr(TEST_SECRET),
            jwt_access_token_expire_minutes=15,
            jwt_issuer="test-issuer",
        ),
    )


def test_login_returns_short_lived_jwt(jwt_settings: None) -> None:
    hasher = PasswordHash.recommended()
    user = SimpleNamespace(
        id=42,
        email="person@example.com",
        password_hash=hasher.hash("correct horse battery staple"),
        is_active=True,
    )
    repository = StubUserRepository(user)

    result = asyncio.run(
        AuthService(repository).login(
            LoginRequest(email=" Person@Example.com ", password="correct horse battery staple")
        )
    )

    claims = jwt.decode(
        result.access_token,
        TEST_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer="test-issuer",
        options={"require": ["sub", "iss", "iat", "nbf", "exp", "jti"]},
    )
    assert result.token_type == "bearer"
    assert result.expires_in == 900
    assert claims["sub"] == "42"
    assert repository.requested_email == "person@example.com"


@pytest.mark.parametrize("user", [None, SimpleNamespace(
    id=42,
    email="person@example.com",
    password_hash=PasswordHash.recommended().hash("correct password"),
    is_active=True,
)])
def test_login_rejects_unknown_user_or_wrong_password(
    jwt_settings: None,
    user: SimpleNamespace | None,
) -> None:
    repository = StubUserRepository(user)

    with pytest.raises(InvalidCredentialsError):
        asyncio.run(
            AuthService(repository).login(
                LoginRequest(email="person@example.com", password="incorrect password")
            )
        )


def test_login_rejects_inactive_user(jwt_settings: None) -> None:
    user = SimpleNamespace(
        id=42,
        email="person@example.com",
        password_hash=PasswordHash.recommended().hash("correct password"),
        is_active=False,
    )

    with pytest.raises(InvalidCredentialsError):
        asyncio.run(
            AuthService(StubUserRepository(user)).login(
                LoginRequest(email="person@example.com", password="correct password")
            )
        )


def test_login_rejects_oauth_only_account_without_local_password(
    jwt_settings: None,
) -> None:
    user = SimpleNamespace(
        id=42,
        email="person@example.com",
        password_hash=None,
        is_active=True,
    )

    with pytest.raises(InvalidCredentialsError):
        asyncio.run(
            AuthService(StubUserRepository(user)).login(
                LoginRequest(
                    email="person@example.com",
                    password="a-valid-length-password",
                )
            )
        )
