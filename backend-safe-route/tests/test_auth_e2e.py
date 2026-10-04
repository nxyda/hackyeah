"""Authentication API flows using isolated dependencies and local PostGIS."""

import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker


TEST_JWT_SECRET = "auth-e2e-signing-key-that-is-at-least-32-bytes"


def _use_test_jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import security

    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret_key=SecretStr(TEST_JWT_SECRET),
            jwt_access_token_expire_minutes=15,
            jwt_issuer="auth-e2e-tests",
        ),
    )


@pytest.mark.integration
@pytest.mark.e2e
def test_register_login_and_protected_request_use_persisted_account(
    run_with_postgis_test_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app.database.session import get_db
        from app.main import app

        _use_test_jwt_settings(monkeypatch)

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                registration = await client.post(
                    "/v1/auth/register",
                    json={
                        "email": "  QA.User@Example.com ",
                        "password": "safe-test-password-123",
                        "given_name": "  Ada ",
                        "family_name": " Lovelace  ",
                    },
                )
                assert registration.status_code == 201, registration.text
                registered = registration.json()
                assert registered["user"]["email"] == "qa.user@example.com"
                assert registered["user"]["given_name"] == "Ada"
                assert registered["user"]["family_name"] == "Lovelace"
                assert "password" not in registered
                assert "password_hash" not in registered

                duplicate = await client.post(
                    "/v1/auth/register",
                    json={
                        "email": "qa.user@example.com",
                        "password": "another-test-password-123",
                    },
                )
                assert duplicate.status_code == 409

                login = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": "QA.User@Example.com",
                        "password": "safe-test-password-123",
                    },
                )
                assert login.status_code == 200, login.text
                assert login.json()["expires_in"] == 900

                protected = await client.get(
                    "/v1/reports",
                    headers={
                        "Authorization": f"Bearer {login.json()['access_token']}"
                    },
                )
                assert protected.status_code == 200, protected.text
                assert protected.json() == []

                bad_password = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": "qa.user@example.com",
                        "password": "incorrect-password",
                    },
                )
                unknown_user = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": "missing@example.com",
                        "password": "incorrect-password",
                    },
                )
                assert bad_password.status_code == 401
                assert unknown_user.status_code == 401
                assert bad_password.json() == unknown_user.json()
                assert bad_password.headers["www-authenticate"] == "Bearer"
        finally:
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)


@pytest.mark.e2e
def test_oauth_provider_outage_returns_sanitized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.database.session import get_db
    from app.main import app
    from app.services import auth_service
    from app.services.oauth_provider_service import OAuthProviderUnavailable

    async def unavailable_provider(provider, credential):
        assert provider.value == "google"
        assert credential == "test-provider-credential"
        raise OAuthProviderUnavailable

    monkeypatch.setattr(
        auth_service,
        "verify_oauth_credential",
        unavailable_provider,
    )

    async def unused_database_session():
        yield object()

    app.dependency_overrides[get_db] = unused_database_session
    try:
        async def request() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/v1/auth/oauth/google",
                    json={"credential": "test-provider-credential"},
                )

            assert response.status_code == 503
            assert response.json()["detail"] == "OAuth authentication is unavailable"
            assert "credential" not in response.text

        asyncio.run(request())
    finally:
        app.dependency_overrides.pop(get_db, None)
