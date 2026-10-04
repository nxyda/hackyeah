"""Endpointy do zarządzania zgłoszeniami zalogowanego użytkownika."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportCreate, ReportResponse, ReportUpdate
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

report_router = APIRouter(prefix="/reports", tags=["reports"])


def _service(session: AsyncSession) -> ReportService:
    return ReportService(ReportRepository(session))


@report_router.get("/nearby", response_model=list[ReportResponse])
async def list_nearby_reports(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=50_000)] = 1_000,
) -> list[ReportResponse]:
    """Zwraca aktywne, niewygasłe zgłoszenia w promieniu od podanej lokalizacji."""

    return await _service(session).list_nearby_reports(
        latitude=lat,
        longitude=lon,
        radius_m=radius_m,
    )


@report_router.get("", response_model=list[ReportResponse])
async def list_my_reports(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ReportResponse]:
    """Zwraca zgłoszenia należące do zalogowanego użytkownika."""

    return await _service(session).list_reports(user.id)


@report_router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    report: ReportCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Tworzy zgłoszenie przypisane do zalogowanego użytkownika."""

    created = await _service(session).create_report(user.id, report)
    logger.info("Report created user_id=%d report_id=%d", user.id, created.id)
    return created


@report_router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,
    changes: ReportUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Aktualizuje własne zgłoszenie; cudze zgłoszenia zwraca jako 404."""

    report = await _service(session).update_report(user.id, report_id, changes)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    logger.info("Report updated user_id=%d report_id=%d", user.id, report_id)
    return report


@report_router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Usuwa własne zgłoszenie; cudze zgłoszenia zwraca jako 404."""

    deleted = await _service(session).delete_report(user.id, report_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    logger.info("Report deleted user_id=%d report_id=%d", user.id, report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@report_router.post("/{report_id}/confirm", response_model=ReportResponse)
async def confirm_report(
    report_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Potwierdza cudze, aktywne zgłoszenie zalogowanego użytkownika."""

    report = await _service(session).confirm_report(user.id, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or cannot be confirmed",
        )
    logger.info("Report confirmation processed user_id=%d report_id=%d", user.id, report_id)
    return report
