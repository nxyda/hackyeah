"""Testy weryfikacji poświadczeń otrzymanych od dostawców OAuth."""

import asyncio
import time
from types import SimpleNamespace

import google.auth.exceptions
import httpx
import pytest
from pydantic import SecretStr

from app.enums.oauth_provider import OAuthProvider
from app.services import oauth_provider_service
from app.services.oauth_provider_service import (
    InvalidOAuthCredential,
    OAuthConfigurationError,
    OAuthProviderUnavailable,
    verify_oauth_credential,
)


def test_google_requires_a_verified_email_and_uses_server_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="mobile-client-id",
            facebook_app_id="",
            facebook_app_secret=SecretStr(""),
            facebook_graph_api_version="v23.0",
        ),
    )
    monkeypatch.setattr(
        oauth_provider_service.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: (
            {
                "sub": "google-subject",
                "email": "ada@example.com",
                "email_verified": True,
                "given_name": "Ada",
                "family_name": "Lovelace",
            }
            if audience == "mobile-client-id"
            else {}
        ),
    )

    profile = asyncio.run(
        verify_oauth_credential(OAuthProvider.GOOGLE, "provider-id-token")
    )

    assert profile.provider_user_id == "google-subject"
    assert profile.email == "ada@example.com"
    assert profile.given_name == "Ada"
    assert profile.family_name == "Lovelace"


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, InvalidOAuthCredential),
        (401, InvalidOAuthCredential),
        (503, OAuthProviderUnavailable),
    ],
)
def test_facebook_http_failures_are_classified(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_error: type[Exception],
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="",
            facebook_app_id="facebook-app-id",
            facebook_app_secret=SecretStr("facebook-app-secret"),
            facebook_graph_api_version="v23.0",
        ),
    )

    class FakeResponse:
        is_error = True

        def __init__(self, status: int) -> None:
            self.status_code = status

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse(status_code)

    monkeypatch.setattr(oauth_provider_service.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(expected_error):
        asyncio.run(verify_oauth_credential(OAuthProvider.FACEBOOK, "test-token"))


@pytest.mark.parametrize(
    "token_data",
    [
        {
            "is_valid": False,
            "app_id": "facebook-app-id",
            "user_id": "facebook-subject",
            "expires_at": int(time.time()) + 3600,
        },
        {
            "is_valid": True,
            "app_id": "another-app-id",
            "user_id": "facebook-subject",
            "expires_at": int(time.time()) + 3600,
        },
        {
            "is_valid": True,
            "app_id": "facebook-app-id",
            "user_id": "facebook-subject",
            "expires_at": int(time.time()) - 1,
        },
    ],
)
def test_facebook_rejects_invalid_app_or_expired_tokens(
    monkeypatch: pytest.MonkeyPatch,
    token_data: dict[str, object],
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="",
            facebook_app_id="facebook-app-id",
            facebook_app_secret=SecretStr("facebook-app-secret"),
            facebook_graph_api_version="v23.0",
        ),
    )

    class FakeResponse:
        status_code = 200
        is_error = False

        def json(self) -> dict[str, object]:
            return {"data": token_data}

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            self.request_count = 0

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args, **_kwargs) -> FakeResponse:
            self.request_count += 1
            return FakeResponse()

    client = FakeAsyncClient()
    monkeypatch.setattr(
        oauth_provider_service.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )
    with pytest.raises(InvalidOAuthCredential):
        asyncio.run(verify_oauth_credential(OAuthProvider.FACEBOOK, "test-token"))
    assert client.request_count == 1


def test_facebook_rejects_profile_subject_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="",
            facebook_app_id="facebook-app-id",
            facebook_app_secret=SecretStr("facebook-app-secret"),
            facebook_graph_api_version="v23.0",
        ),
    )

    class FakeResponse:
        status_code = 200
        is_error = False

        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def json(self) -> dict[str, object]:
            return self.payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            self.call_count = 0

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str, **_kwargs) -> FakeResponse:
            self.call_count += 1
            if url.endswith("/debug_token"):
                return FakeResponse(
                    {
                        "data": {
                            "is_valid": True,
                            "app_id": "facebook-app-id",
                            "user_id": "verified-subject",
                            "expires_at": int(time.time()) + 3600,
                        }
                    }
                )
            return FakeResponse(
                {
                    "id": "different-subject",
                    "email": "ada@example.com",
                }
            )

    client = FakeAsyncClient()
    monkeypatch.setattr(
        oauth_provider_service.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )
    with pytest.raises(InvalidOAuthCredential):
        asyncio.run(verify_oauth_credential(OAuthProvider.FACEBOOK, "test-token"))
    assert client.call_count == 2


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectTimeout("private timeout detail"),
        httpx.ConnectError("private connection detail"),
    ],
)
def test_facebook_transport_failures_do_not_leak_request_details(
    monkeypatch: pytest.MonkeyPatch,
    error: httpx.RequestError,
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="",
            facebook_app_id="facebook-app-id",
            facebook_app_secret=SecretStr("facebook-app-secret"),
            facebook_graph_api_version="v23.0",
        ),
    )

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args, **_kwargs):
            raise error

    monkeypatch.setattr(oauth_provider_service.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(OAuthProviderUnavailable) as provider_error:
        asyncio.run(verify_oauth_credential(OAuthProvider.FACEBOOK, "test-token"))
    assert "private" not in str(provider_error.value)


def test_google_rejects_unverified_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="mobile-client-id",
            facebook_app_id="",
            facebook_app_secret=SecretStr(""),
            facebook_graph_api_version="v23.0",
        ),
    )
    monkeypatch.setattr(
        oauth_provider_service.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: {
            "sub": "google-subject",
            "email": "ada@example.com",
            "email_verified": False,
        },
    )

    with pytest.raises(InvalidOAuthCredential):
        asyncio.run(
            verify_oauth_credential(OAuthProvider.GOOGLE, "provider-id-token")
        )


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"sub": "", "email": "ada@example.com", "email_verified": True},
        {"sub": "google-subject", "email": "", "email_verified": True},
        {
            "sub": "google-subject",
            "email": "not-an-email",
            "email_verified": True,
        },
    ],
)
def test_google_rejects_missing_or_invalid_identity_claims(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(google_client_id="mobile-client-id"),
    )
    monkeypatch.setattr(
        oauth_provider_service.id_token,
        "verify_oauth2_token",
        lambda *_args: claims,
    )

    with pytest.raises(InvalidOAuthCredential):
        asyncio.run(verify_oauth_credential(OAuthProvider.GOOGLE, "test-token"))


def test_google_provider_errors_are_classified_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(google_client_id="mobile-client-id"),
    )

    def reject_credential(*_args):
        raise ValueError("private credential detail")

    monkeypatch.setattr(
        oauth_provider_service.id_token,
        "verify_oauth2_token",
        reject_credential,
    )
    with pytest.raises(InvalidOAuthCredential) as invalid_error:
        asyncio.run(verify_oauth_credential(OAuthProvider.GOOGLE, "test-token"))
    assert "private credential detail" not in str(invalid_error.value)

    def unavailable(*_args):
        raise google.auth.exceptions.TransportError("private network detail")

    monkeypatch.setattr(
        oauth_provider_service.id_token,
        "verify_oauth2_token",
        unavailable,
    )
    with pytest.raises(OAuthProviderUnavailable) as unavailable_error:
        asyncio.run(verify_oauth_credential(OAuthProvider.GOOGLE, "test-token"))
    assert "private network detail" not in str(unavailable_error.value)


@pytest.mark.parametrize(
    ("provider", "settings"),
    [
        (
            OAuthProvider.GOOGLE,
            SimpleNamespace(
                google_client_id="",
                facebook_app_id="",
                facebook_app_secret=SecretStr(""),
                facebook_graph_api_version="v23.0",
            ),
        ),
        (
            OAuthProvider.FACEBOOK,
            SimpleNamespace(
                google_client_id="",
                facebook_app_id="facebook-app-id",
                facebook_app_secret=SecretStr(""),
                facebook_graph_api_version="v23.0",
            ),
        ),
    ],
)
def test_oauth_missing_provider_configuration_fails_before_network(
    monkeypatch: pytest.MonkeyPatch,
    provider: OAuthProvider,
    settings: SimpleNamespace,
) -> None:
    monkeypatch.setattr(oauth_provider_service, "get_settings", lambda: settings)

    def unexpected_client(*_args, **_kwargs):
        raise AssertionError("OAuth configuration errors must not make requests")

    monkeypatch.setattr(oauth_provider_service.httpx, "AsyncClient", unexpected_client)
    with pytest.raises(OAuthConfigurationError):
        asyncio.run(verify_oauth_credential(provider, "test-token"))


def test_facebook_verifies_app_ownership_and_profile_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        oauth_provider_service,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="",
            facebook_app_id="facebook-app-id",
            facebook_app_secret=SecretStr("facebook-app-secret"),
            facebook_graph_api_version="v23.0",
        ),
    )

    class FakeResponse:
        status_code = 200
        is_error = False

        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def json(self) -> dict[str, object]:
            return self.payload

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(
            self,
            url: str,
            *,
            params: dict[str, str],
            headers: dict[str, str] | None = None,
        ) -> FakeResponse:
            if url.endswith("/debug_token"):
                assert params["access_token"] == "facebook-app-id|facebook-app-secret"
                assert params["input_token"] == "facebook-user-token"
                return FakeResponse(
                    {
                        "data": {
                            "is_valid": True,
                            "app_id": "facebook-app-id",
                            "user_id": "facebook-subject",
                            "expires_at": int(time.time()) + 3600,
                        }
                    }
                )

            assert headers == {"Authorization": "Bearer facebook-user-token"}
            return FakeResponse(
                {
                    "id": "facebook-subject",
                    "email": "ada@example.com",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                }
            )

    monkeypatch.setattr(oauth_provider_service.httpx, "AsyncClient", FakeAsyncClient)

    profile = asyncio.run(
        verify_oauth_credential(OAuthProvider.FACEBOOK, "facebook-user-token")
    )

    assert profile.provider is OAuthProvider.FACEBOOK
    assert profile.provider_user_id == "facebook-subject"
    assert profile.email == "ada@example.com"
