from datetime import datetime, timezone

from geoalchemy2 import Geography
from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.report import ReportCategory, ReportStatus
from app.models.report import Report
from app.models.report_confirmation import ReportConfirmation
from app.repositories.base_repository import BaseRepository
from app.spatial import geography_point, metric_route_corridor, point_wkt


class ReportRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, report_id: int) -> Report | None:
        stmt = select(Report).where(Report.id == report_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self,
        report_id: int,
        user_id: int,
    ) -> tuple[Report, float, float] | None:
        stmt = select(
            Report,
            func.ST_Y(Report.geom).label("latitude"),
            func.ST_X(Report.geom).label("longitude"),
        ).where(Report.id == report_id, Report.user_id == user_id)
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row.latitude, row.longitude

    async def list_for_user(
        self,
        user_id: int,
    ) -> list[tuple[Report, float, float]]:
        stmt = (
            select(
                Report,
                func.ST_Y(Report.geom).label("latitude"),
                func.ST_X(Report.geom).label("longitude"),
            )
            .where(Report.user_id == user_id)
            .order_by(Report.created_at.desc(), Report.id.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], row.latitude, row.longitude) for row in result.all()]

    async def get_by_user(
        self,
        user_id: int,
    ) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def create(
        self,
        *,
        user_id: int,
        category: ReportCategory,
        latitude: float,
        longitude: float,
        expires_at: datetime | None = None,
    ) -> Report:
        report = Report(
            user_id=user_id,
            category=category,
            geom=point_wkt(longitude, latitude),
            expires_at=expires_at,
        )

        self.session.add(report)

        await self.session.flush()

        return report

    async def update_for_user(
        self,
        *,
        report_id: int,
        user_id: int,
        category: ReportCategory | None,
        latitude: float | None,
        longitude: float | None,
    ) -> tuple[Report, float, float] | None:
        values: dict[str, object] = {}
        if category is not None:
            values["category"] = category
        if latitude is not None and longitude is not None:
            values["geom"] = point_wkt(longitude, latitude)

        result = await self.session.execute(
            update(Report)
            .where(Report.id == report_id, Report.user_id == user_id)
            .values(**values)
        )
        if result.rowcount == 0:
            return None

        await self.session.flush()
        return await self.get_by_id_for_user(report_id, user_id)

    async def delete_for_user(self, report_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Report).where(Report.id == report_id, Report.user_id == user_id)
        )
        return result.rowcount > 0

    async def confirm(
        self,
        report_id: int,
        user_id: int,
    ) -> tuple[Report, float, float] | None:
        eligible = (
            Report.id == report_id,
            Report.user_id != user_id,
            Report.status == ReportStatus.ACTIVE,
            (Report.expires_at.is_(None)) | (Report.expires_at > func.now()),
        )
        inserted = await self.session.execute(
            insert(ReportConfirmation)
            .from_select(
                ["report_id", "user_id"],
                select(Report.id, literal(user_id)).where(*eligible),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    ReportConfirmation.report_id,
                    ReportConfirmation.user_id,
                ]
            )
            .returning(ReportConfirmation.report_id)
        )
        was_new_confirmation = inserted.scalar_one_or_none() is not None

        if was_new_confirmation:
            await self.session.execute(
                update(Report)
                .where(*eligible)
                .values(confirmations=Report.confirmations + 1)
                .execution_options(synchronize_session=False)
            )

        result = await self.session.execute(
            select(
                Report,
                func.ST_Y(Report.geom).label("latitude"),
                func.ST_X(Report.geom).label("longitude"),
            )
            .where(*eligible)
            .execution_options(populate_existing=True)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row.latitude, row.longitude

    async def get_active_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[tuple[Report, float, float]]:
        point = geography_point(longitude, latitude)

        stmt = (
            select(
                Report,
                func.ST_Y(Report.geom).label("latitude"),
                func.ST_X(Report.geom).label("longitude"),
            )
            .where(
                Report.status == ReportStatus.ACTIVE,
                Report.created_at <= func.now(),
                func.ST_DWithin(
                    Report.geom.cast(Geography),
                    point,
                    radius_m,
                ),
                (
                    (Report.expires_at.is_(None))
                    | (Report.expires_at > func.now())
                ),
            )
            .order_by(
                func.ST_Distance(
                    Report.geom.cast(Geography),
                    point,
                ),
                Report.id,
            )
        )

        result = await self.session.execute(stmt)

        return [
            (row[0], row.latitude, row.longitude)
            for row in result.all()
        ]

    async def get_active_in_corridor(
        self,
        route_wkt: str,
        buffer_m: float = 3000.0,
        departure_time: datetime | None = None,
    ) -> list[Report]:
        """Pobiera aktywne i niewygasłe zgłoszenia z korytarza trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        effective_time = departure_time or datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Report).where(
                Report.status == ReportStatus.ACTIVE,
                Report.created_at <= effective_time,
                (Report.expires_at.is_(None)) | (Report.expires_at > effective_time),
                func.ST_Intersects(Report.geom, corridor),
            )
        )
        return list(result.scalars().all())

    async def count_active_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
        departure_time: datetime,
    ) -> int:
        point = geography_point(longitude, latitude)

        stmt = select(func.count(Report.id)).where(
            Report.status == ReportStatus.ACTIVE,
            func.ST_DWithin(
                Report.geom.cast(Geography),
                point,
                radius_m,
            ),
            (
                (Report.expires_at.is_(None))
                | (Report.expires_at > departure_time)
            ),
        )

        result = await self.session.execute(stmt)

        return result.scalar_one()