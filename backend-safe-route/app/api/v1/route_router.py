"""Router HTTP odpowiedzialny za endpoint planowania trasy."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.integrations.mapbox_directions_client import MapboxDirectionsError
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import RouteService, RouteUnavailableError

logger = logging.getLogger(__name__)

route_router = APIRouter(tags=["route"])


@route_router.post("/route", response_model=RouteResponse)
async def create_route(
    request: RouteRequest,
    session: AsyncSession = Depends(get_db),
) -> RouteResponse:
    """Przekazuje żądanie do RouteService i zwraca wynik."""

    try:
        return await RouteService(session).calculate_route(request)
    except ValueError as exc:
        logger.info("Route request rejected reason=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (MapboxDirectionsError, RouteUnavailableError) as exc:
        logger.warning("Route provider unavailable error=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Route planning is temporarily unavailable",
        ) from None
