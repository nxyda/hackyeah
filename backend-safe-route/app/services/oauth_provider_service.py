"""Weryfikacja poświadczeń Google i Facebook otrzymanych od klienta mobilnego."""

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import partial

import google.auth.exceptions
import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.config import get_settings
from app.enums.oauth_provider import OAuthProvider

logger = logging.getLogger(__name__)


class InvalidOAuthCredential(Exception):
    """Token dostawcy OAuth jest nieważny albo nie potwierdza tożsamości."""


class OAuthProviderUnavailable(Exception):
    """Nie udało się zweryfikować tokenu u zewnętrznego dostawcy."""


class OAuthConfigurationError(Exception):
    """Brakuje konfiguracji klienta OAuth po stronie serwera."""


@dataclass(frozen=True)
class OAuthProfile:
    provider: OAuthProvider
    provider_user_id: str
    email: str
    given_name: str | None
    family_name: str | None


async def verify_oauth_credential(
    provider: OAuthProvider,
    credential: str,
) -> OAuthProfile:
    """Weryfikuje token dostawcy i zwraca wyłącznie zweryfikowane dane profilu."""

    settings = get_settings()
    if provider is OAuthProvider.GOOGLE:
        if not settings.google_client_id:
            raise OAuthConfigurationError
        return await _verify_google(credential, settings.google_client_id)

    app_secret = settings.facebook_app_secret.get_secret_value()
    if not settings.facebook_app_id or not app_secret:
        raise OAuthConfigurationError
    return await _verify_facebook(
        credential,
        settings.facebook_app_id,
        app_secret,
        settings.facebook_graph_api_version,
    )


async def _verify_google(credential: str, client_id: str) -> OAuthProfile:
    try:
        claims = await asyncio.to_thread(
            id_token.verify_oauth2_token,
            credential,
            partial(GoogleRequest(), timeout=5),
            client_id,
        )
    except ValueError as exc:
        logger.info("Google credential rejected error=%s", type(exc).__name__)
        raise InvalidOAuthCredential from None
    except google.auth.exceptions.GoogleAuthError as exc:
        logger.warning(
            "Google token verification unavailable error=%s",
            type(exc).__name__,
        )
        raise OAuthProviderUnavailable from None

    subject = claims.get("sub")
    email = claims.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or not email
        or claims.get("email_verified") is not True
    ):
        raise InvalidOAuthCredential

    return OAuthProfile(
        provider=OAuthProvider.GOOGLE,
        provider_user_id=subject,
        email=_validated_email(email),
        given_name=_optional_name(claims.get("given_name")),
        family_name=_optional_name(claims.get("family_name")),
    )


async def _verify_facebook(
    credential: str,
    app_id: str,
    app_secret: str,
    graph_version: str,
) -> OAuthProfile:
    base_url = f"https://graph.facebook.com/{graph_version}"
    timeout = httpx.Timeout(5.0, connect=2.0)
    app_access_token = f"{app_id}|{app_secret}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        debug = await _facebook_get(
            client,
            f"{base_url}/debug_token",
            params={
                "input_token": credential,
                "access_token": app_access_token,
            },
        )
        token_data = debug.get("data")
        if not isinstance(token_data, dict):
            raise OAuthProviderUnavailable

        expires_at = token_data.get("expires_at")
        if (
            token_data.get("is_valid") is not True
            or str(token_data.get("app_id")) != app_id
            or not isinstance(token_data.get("user_id"), str)
            or not token_data["user_id"]
            or not isinstance(expires_at, int)
            or (expires_at != 0 and expires_at <= int(time.time()))
        ):
            raise InvalidOAuthCredential

        profile = await _facebook_get(
            client,
            f"{base_url}/me",
            headers={"Authorization": f"Bearer {credential}"},
            params={"fields": "id,email,first_name,last_name"},
        )

    if (
        profile.get("id") != token_data["user_id"]
        or not isinstance(profile.get("email"), str)
        or not profile["email"]
    ):
        raise InvalidOAuthCredential

    return OAuthProfile(
        provider=OAuthProvider.FACEBOOK,
        provider_user_id=token_data["user_id"],
        email=_validated_email(profile["email"]),
        given_name=_optional_name(profile.get("first_name")),
        family_name=_optional_name(profile.get("last_name")),
    )


async def _facebook_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as exc:
        logger.warning(
            "Facebook token verification request failed error=%s",
            type(exc).__name__,
        )
        raise OAuthProviderUnavailable from None

    if response.status_code == 401 or response.status_code == 400:
        logger.info("Facebook rejected OAuth credential status=%d", response.status_code)
        raise InvalidOAuthCredential
    if response.status_code >= 500:
        logger.warning("Facebook OAuth service unavailable status=%d", response.status_code)
        raise OAuthProviderUnavailable
    if response.is_error:
        logger.warning("Facebook OAuth request failed status=%d", response.status_code)
        raise OAuthProviderUnavailable

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning(
            "Facebook OAuth response was not valid JSON error=%s",
            type(exc).__name__,
        )
        raise OAuthProviderUnavailable from None
    if not isinstance(payload, dict):
        logger.warning("Facebook OAuth response had an unexpected JSON shape")
        raise OAuthProviderUnavailable
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, dict) and error.get("code") in {190, 102}:
            logger.info("Facebook rejected OAuth credential")
            raise InvalidOAuthCredential
        logger.warning("Facebook OAuth API returned an error payload")
        raise OAuthProviderUnavailable
    return payload


def _optional_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    return name[:100] or None


def _validated_email(value: str) -> str:
    try:
        return str(TypeAdapter(EmailStr).validate_python(value)).lower()
    except ValidationError:
        raise InvalidOAuthCredential from None
