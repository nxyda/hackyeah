"""Authenticated endpoints for temporary location sharing."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.location_share_repository import LocationShareRepository
from app.schemas.location_share import (
    LocationShareCreate,
    LocationShareResponse,
    LocationUpdate,
    SharedLocationResponse,
)
from app.services.location_share_service import (
    ActiveLocationShareExistsError,
    LocationShareCodeCapacityError,
    LocationShareNotFoundError,
    LocationShareService,
)

location_share_router = APIRouter(prefix="/location-shares", tags=["location sharing"])


def _service(session: AsyncSession) -> LocationShareService:
    return LocationShareService(LocationShareRepository(session))


@location_share_router.post(
    "",
    response_model=LocationShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location_share(
    request: LocationShareCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LocationShareResponse:
    """Starts a timed share and returns the owner's four-digit access code."""

    try:
        return await _service(session).create(user.id, request)
    except ActiveLocationShareExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active location share already exists",
        ) from None
    except LocationShareCodeCapacityError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No location-sharing codes are currently available",
        ) from None


@location_share_router.get("/current", response_model=LocationShareResponse)
async def get_current_location_share(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LocationShareResponse:
    """Returns the active share belonging to the current user."""

    try:
        return await _service(session).get_current(user.id)
    except LocationShareNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location share not found",
        ) from None


@location_share_router.put("/current/location", response_model=LocationShareResponse)
async def update_current_location(
    location: LocationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LocationShareResponse:
    """Updates only the owner's latest location; the share code and expiry remain unchanged."""

    try:
        return await _service(session).update_location(user.id, location)
    except LocationShareNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location share not found",
        ) from None


@location_share_router.get("/{code}", response_model=SharedLocationResponse)
async def read_shared_location(
    code: Annotated[str, Path(pattern=r"^\d{4}$")],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SharedLocationResponse:
    """Reads the latest location using a share code; it does not grant write access."""

    try:
        return await _service(session).get_shared_location(user.id, code)
    except LocationShareNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location share not found",
        ) from None


@location_share_router.delete(
    "/current",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_current_location_share(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Revokes the owner's share immediately."""

    try:
        await _service(session).revoke(user.id)
    except LocationShareNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location share not found",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
