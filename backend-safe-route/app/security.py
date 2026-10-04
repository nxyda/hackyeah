"""Wspólna obsługa podpisywania i weryfikacji tokenów dostępu."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import get_settings

JWT_ALGORITHM = "HS256"


class AuthConfigurationError(Exception):
    """Konfiguracja klucza JWT nie spełnia wymagań bezpieczeństwa."""


def _signing_key() -> str:
    key = get_settings().jwt_secret_key.get_secret_value()
    if len(key.encode("utf-8")) < 32:
        raise AuthConfigurationError
    return key


def create_access_token(user_id: int) -> tuple[str, int]:
    """Podpisuje JWT użytkownika i zwraca token oraz jego czas życia w sekundach."""

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "iss": settings.jwt_issuer,
            "iat": now,
            "nbf": now,
            "exp": expires_at,
            "jti": secrets.token_urlsafe(16),
        },
        _signing_key(),
        algorithm=JWT_ALGORITHM,
    )
    return token, settings.jwt_access_token_expire_minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    """Weryfikuje podpis, wystawcę, terminy ważności i wymagane claimy JWT."""

    settings = get_settings()
    return jwt.decode(
        token,
        _signing_key(),
        algorithms=[JWT_ALGORITHM],
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "iss", "iat", "nbf", "exp", "jti"]},
    )
