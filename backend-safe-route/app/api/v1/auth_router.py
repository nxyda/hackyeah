"""Endpointy rejestracji i uwierzytelniania."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.enums.oauth_provider import OAuthProvider
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    OAuthLoginRequest,
    RegisterRequest,
    RegistrationResponse,
    TokenResponse,
)
from app.security import AuthConfigurationError
from app.services.auth_service import (
    AuthService,
    DuplicateAccountError,
    InvalidCredentialsError,
)
from app.services.oauth_provider_service import (
    InvalidOAuthCredential,
    OAuthConfigurationError,
    OAuthProviderUnavailable,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _service(session: AsyncSession) -> AuthService:
    return AuthService(UserRepository(session))


def _authentication_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured",
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Loguje użytkownika i zwraca token dostępu JWT."""

    try:
        return await _service(session).login(credentials)
    except InvalidCredentialsError:
        logger.warning("Login rejected: invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except AuthConfigurationError:
        raise _authentication_unavailable() from None


@auth_router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    details: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegistrationResponse:
    """Tworzy konto lokalne i zwraca token oraz podstawowe dane profilu."""

    try:
        return await _service(session).register(details)
    except DuplicateAccountError:
        logger.info("Registration rejected: account already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    except AuthConfigurationError:
        raise _authentication_unavailable() from None


@auth_router.post(
    "/oauth/{provider}",
    response_model=RegistrationResponse,
)
async def login_with_oauth(
    provider: OAuthProvider,
    credentials: OAuthLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegistrationResponse:
    """Weryfikuje token Google/Facebook, loguje lub tworzy konto."""

    try:
        return await _service(session).login_with_oauth(
            provider,
            credentials.credential,
        )
    except InvalidOAuthCredential:
        logger.warning(
            "OAuth login rejected: invalid provider credential provider=%s",
            provider.value,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unverified provider credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except InvalidCredentialsError:
        logger.warning(
            "OAuth login rejected: inactive account provider=%s",
            provider.value,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except DuplicateAccountError:
        logger.info(
            "OAuth registration rejected: account already exists provider=%s",
            provider.value,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists; sign in with its existing method",
        ) from None
    except (OAuthConfigurationError, OAuthProviderUnavailable, AuthConfigurationError) as exc:
        logger.error(
            "OAuth authentication unavailable provider=%s error=%s",
            provider.value,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth authentication is unavailable",
        ) from None
