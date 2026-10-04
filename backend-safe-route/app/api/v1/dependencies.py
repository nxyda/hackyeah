"""Zależności HTTP używane przez chronione endpointy API v1."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.enums.user_role import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security import AuthConfigurationError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Weryfikuje JWT i sprawdza, czy konto nadal jest aktywne."""

    if credentials is None:
        raise _unauthorized()

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
        if user_id < 1:
            raise ValueError("Invalid subject")
    except AuthConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


async def get_current_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """Wymaga aktywnego konta administratora."""

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return user
