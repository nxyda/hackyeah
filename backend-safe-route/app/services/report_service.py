"""Serwis przypadków użycia zgłoszeń bezpieczeństwa."""

from app.models.report import Report
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportCreate, ReportResponse, ReportUpdate


class ReportService:
    """Obsługuje zgłoszenia użytkownika przez repozytorium."""

    def __init__(self, repository: ReportRepository) -> None:
        self.repository = repository

    @staticmethod
    def _to_response(row: tuple[Report, float, float]) -> ReportResponse:
        report, latitude, longitude = row
        return ReportResponse(
            id=report.id,
            category=report.category,
            lat=latitude,
            lon=longitude,
            created_at=report.created_at,
            expires_at=report.expires_at,
            status=report.status,
            confirmations=report.confirmations,
        )

    async def list_reports(self, user_id: int) -> list[ReportResponse]:
        rows = await self.repository.list_for_user(user_id)
        return [self._to_response(row) for row in rows]

    async def list_nearby_reports(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: float,
    ) -> list[ReportResponse]:
        rows = await self.repository.get_active_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
        )
        return [self._to_response(row) for row in rows]

    async def create_report(
        self,
        user_id: int,
        report: ReportCreate,
    ) -> ReportResponse:
        created = await self.repository.create(
            user_id=user_id,
            category=report.category,
            latitude=report.lat,
            longitude=report.lon,
        )
        row = await self.repository.get_by_id_for_user(created.id, user_id)
        if row is None:
            raise RuntimeError("Created report could not be retrieved")
        await self.repository.session.commit()
        return self._to_response(row)

    async def update_report(
        self,
        user_id: int,
        report_id: int,
        changes: ReportUpdate,
    ) -> ReportResponse | None:
        row = await self.repository.update_for_user(
            report_id=report_id,
            user_id=user_id,
            category=changes.category,
            latitude=changes.lat,
            longitude=changes.lon,
        )
        if row is None:
            return None
        await self.repository.session.commit()
        return self._to_response(row)

    async def delete_report(self, user_id: int, report_id: int) -> bool:
        deleted = await self.repository.delete_for_user(report_id, user_id)
        if deleted:
            await self.repository.session.commit()
        return deleted

    async def confirm_report(
        self,
        user_id: int,
        report_id: int,
    ) -> ReportResponse | None:
        row = await self.repository.confirm(report_id, user_id)
        if row is None:
            return None
        await self.repository.session.commit()
        return self._to_response(row)
