"""HTTP endpoints for street lamps."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.street_lamp_repository import StreetLampRepository
from app.schemas.street_lamp import NearbyStreetLampResponse, StreetLampResponse
from app.services.street_lamp_service import StreetLampService

logger = logging.getLogger(__name__)
street_lamp_router = APIRouter(prefix="/street-lamps", tags=["street-lamps"])


@street_lamp_router.get("/nearby", response_model=list[NearbyStreetLampResponse])
async def get_nearby_street_lamps(
    session: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=50_000)] = 1_000,
) -> list[NearbyStreetLampResponse]:
    """Returns street lamps within the requested radius, nearest first."""

    try:
        return await StreetLampService(StreetLampRepository(session)).get_nearby(
            longitude=lon,
            latitude=lat,
            radius_m=radius_m,
        )
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve nearby street lamps error=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve street lamps",
        ) from exc


@street_lamp_router.get("/{lamp_id}", response_model=StreetLampResponse)
async def get_street_lamp(
    lamp_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreetLampResponse:
    """Returns a street lamp by its database identifier."""

    try:
        lamp = await StreetLampService(StreetLampRepository(session)).get_by_id(lamp_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve street lamp lamp_id=%s error=%s", lamp_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve street lamp",
        ) from exc
    if lamp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Street lamp not found")
    return lamp
