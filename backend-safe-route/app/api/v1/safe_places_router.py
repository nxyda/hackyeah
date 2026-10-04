"""HTTP endpoints for querying safe places."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.safe_place_repository import SafePlaceRepository
from app.schemas.safe_place import NearbySafePlaceResponse, SafePlaceResponse
from app.services.safe_place_service import SafePlaceService

logger = logging.getLogger(__name__)

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0
MIN_SEARCH_RADIUS_M = 0.0
DEFAULT_SEARCH_RADIUS_M = 1_000.0
MAX_SEARCH_RADIUS_M = 50_000.0

safe_place_router = APIRouter(prefix="/safe-places", tags=["safe-places"])


def _service(session: AsyncSession) -> SafePlaceService:
    return SafePlaceService(SafePlaceRepository(session))


@safe_place_router.get(
    "/nearby",
    response_model=list[NearbySafePlaceResponse],
)
async def get_nearby_safe_places(
    session: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=MIN_LATITUDE, le=MAX_LATITUDE)],
    lon: Annotated[float, Query(ge=MIN_LONGITUDE, le=MAX_LONGITUDE)],
    radius_m: Annotated[
        float,
        Query(gt=MIN_SEARCH_RADIUS_M, le=MAX_SEARCH_RADIUS_M),
    ] = DEFAULT_SEARCH_RADIUS_M,
) -> list[NearbySafePlaceResponse]:
    """Returns safe places within the requested radius, nearest first."""

    try:
        return await _service(session).get_nearby(
            longitude=lon,
            latitude=lat,
            radius_m=radius_m,
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to retrieve nearby safe places error=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve safe places",
        ) from exc


@safe_place_router.get(
    "/{safe_place_id}",
    response_model=SafePlaceResponse,
)
async def get_safe_place(
    safe_place_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SafePlaceResponse:
    """Returns a safe place by its database identifier."""

    try:
        safe_place = await _service(session).get_by_id(safe_place_id)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to retrieve safe place safe_place_id=%s error=%s",
            safe_place_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve safe place",
        ) from exc

    if safe_place is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safe place not found",
        )
    return safe_place
