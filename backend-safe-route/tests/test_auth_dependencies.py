"""Testy weryfikacji JWT przed dostępem do chronionego API."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.v1 import dependencies
from app.main import app
from app import security
from app.security import JWT_ALGORITHM

TEST_SECRET = "test-secret-key-that-is-at-least-32-bytes"


def _token(*, expires_in: int = 60) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "7",
            "iss": "test-issuer",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=expires_in),
            "jti": "test-token",
        },
        TEST_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def _credentials(*, expires_in: int = 60) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token(expires_in=expires_in))


def test_current_user_requires_a_valid_token_and_active_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=7, is_active=True)
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret_key=SecretStr(TEST_SECRET),
            jwt_issuer="test-issuer",
        ),
    )

    class StubUserRepository:
        def __init__(self, session: object) -> None:
            pass

        async def get_by_id(self, user_id: int) -> SimpleNamespace | None:
            assert user_id == user.id
            return user

    monkeypatch.setattr(dependencies, "UserRepository", StubUserRepository)

    assert asyncio.run(dependencies.get_current_user(_credentials(), object())) is user

    with pytest.raises(HTTPException) as error:
        asyncio.run(dependencies.get_current_user(_credentials(expires_in=-1), object()))
    assert error.value.status_code == 401

    user.is_active = False
    with pytest.raises(HTTPException) as error:
        asyncio.run(dependencies.get_current_user(_credentials(), object()))
    assert error.value.status_code == 401


def test_reports_endpoint_rejects_requests_without_a_bearer_token() -> None:
    response = TestClient(app).get("/v1/reports")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
