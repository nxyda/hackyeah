"""Operacje administracyjne dostępne wyłącznie dla administratorów."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_admin_user
from app.database.session import get_db
from app.enums.user_role import UserRole
from app.models.user import User
from app.schemas.admin import (
    AdminPasswordUpdate,
    AdminUserResponse,
    AdminUserUpdate,
)
from app.services.auth_service import password_hasher

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])


async def _locked_active_admins_other_than(
    session: AsyncSession,
    user_id: int,
) -> int:
    result = await session.execute(
        select(User.id)
        .where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        .order_by(User.id)
        .with_for_update()
    )
    return sum(admin_id != user_id for admin_id in result.scalars().all())


@admin_router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[User]:
    """Zwraca użytkowników bez hashy haseł."""

    result = await session.execute(select(User).order_by(User.id))
    return list(result.scalars().all())


@admin_router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    changes: AdminUserUpdate,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Aktualizuje profil, status lub rolę użytkownika."""

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = changes.role if changes.role is not None else user.role
    new_is_active = changes.is_active if changes.is_active is not None else user.is_active
    if (
        user.role == UserRole.ADMIN
        and user.is_active
        and (new_role != UserRole.ADMIN or not new_is_active)
        and await _locked_active_admins_other_than(session, user.id) == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot deactivate or demote the last active administrator",
        )

    for field in ("given_name", "family_name", "is_active", "role"):
        if field in changes.model_fields_set:
            setattr(user, field, getattr(changes, field))

    await session.commit()
    await session.refresh(user)
    logger.info("Admin updated user admin_id=%d user_id=%d", admin.id, user.id)
    return user


@admin_router.put(
    "/users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_user_password(
    user_id: int,
    changes: AdminPasswordUpdate,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Ustawia nowe hasło lokalne bez ujawniania jego hasha."""

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = await asyncio.to_thread(
        password_hasher.hash,
        changes.password,
    )
    await session.commit()
    logger.info("Admin reset password admin_id=%d user_id=%d", admin.id, user.id)


@admin_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Usuwa konto, zachowując co najmniej jednego aktywnego administratora."""

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot delete their own account",
        )
    if (
        user.role == UserRole.ADMIN
        and user.is_active
        and await _locked_active_admins_other_than(session, user.id) == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last active administrator",
        )

    await session.delete(user)
    await session.commit()
    logger.info("Admin deleted user admin_id=%d user_id=%d", admin.id, user_id)
