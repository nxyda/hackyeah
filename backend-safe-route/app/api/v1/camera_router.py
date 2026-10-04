"""HTTP endpoints for monitoring cameras."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.camera_repository import CameraRepository
from app.schemas.camera import CameraResponse, NearbyCameraResponse
from app.services.camera_service import CameraService

logger = logging.getLogger(__name__)
camera_router = APIRouter(prefix="/cameras", tags=["cameras"])


@camera_router.get("/nearby", response_model=list[NearbyCameraResponse])
async def get_nearby_cameras(
    session: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=50_000)] = 1_000,
) -> list[NearbyCameraResponse]:
    """Returns cameras within the requested radius, nearest first."""

    try:
        return await CameraService(CameraRepository(session)).get_nearby(
            longitude=lon,
            latitude=lat,
            radius_m=radius_m,
        )
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve nearby cameras error=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve cameras",
        ) from exc


@camera_router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CameraResponse:
    """Returns a camera by its database identifier."""

    try:
        camera = await CameraService(CameraRepository(session)).get_by_id(camera_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to retrieve camera camera_id=%s error=%s", camera_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve camera",
        ) from exc
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera
