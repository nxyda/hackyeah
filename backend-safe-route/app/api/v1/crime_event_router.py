"""HTTP endpoints for historical crime events."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.crime_event_repository import CrimeEventRepository
from app.schemas.crime_event import CrimeEventResponse, NearbyCrimeEventResponse
from app.services.crime_event_service import CrimeEventService

logger = logging.getLogger(__name__)
crime_event_router = APIRouter(prefix="/crime-events", tags=["crime-events"])


@crime_event_router.get("/nearby", response_model=list[NearbyCrimeEventResponse])
async def get_nearby_crime_events(
    session: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=50_000)] = 1_000,
    occurred_after: datetime | None = None,
    occurred_before: datetime | None = None,
) -> list[NearbyCrimeEventResponse]:
    """Returns historical crime events within a radius, nearest first."""

    try:
        return await CrimeEventService(CrimeEventRepository(session)).get_nearby(
            longitude=lon,
            latitude=lat,
            radius_m=radius_m,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve nearby crime events error=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve crime events",
        ) from exc


@crime_event_router.get("/{event_id}", response_model=CrimeEventResponse)
async def get_crime_event(
    event_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CrimeEventResponse:
    """Returns a historical crime event by its database identifier."""

    try:
        event = await CrimeEventService(CrimeEventRepository(session)).get_by_id(event_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve crime event event_id=%s error=%s", event_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve crime event",
        ) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crime event not found")
    return event
