from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crime_event import CrimeEvent
from app.repositories.base_repository import BaseRepository
from app.repositories.spatial import CrimeEventWithDistance
from app.spatial import geography_point, metric_route_corridor


class CrimeEventRepository(BaseRepository):
    """Repozytorium zdarzeń kryminalnych."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(
        self,
        event_id: int,
    ) -> tuple[CrimeEvent, float, float] | None:
        stmt = select(
            CrimeEvent,
            func.ST_Y(CrimeEvent.geom).label("latitude"),
            func.ST_X(CrimeEvent.geom).label("longitude"),
        ).where(
            CrimeEvent.id == event_id,
        )

        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        event, latitude, longitude = row
        return event, float(latitude), float(longitude)

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[CrimeEventWithDistance]:
        point = geography_point(longitude, latitude)

        distance = func.ST_Distance(
            CrimeEvent.geom.cast(Geography),
            point,
        ).label("distance_m")

        conditions = [
            func.ST_DWithin(
                CrimeEvent.geom.cast(Geography),
                point,
                radius_m,
            ),
        ]

        if occurred_after is not None:
            conditions.append(
                CrimeEvent.occurred_at >= occurred_after,
            )

        if occurred_before is not None:
            conditions.append(
                CrimeEvent.occurred_at <= occurred_before,
            )

        stmt = (
            select(
                CrimeEvent,
                distance,
                func.ST_Y(CrimeEvent.geom).label("latitude"),
                func.ST_X(CrimeEvent.geom).label("longitude"),
            )
            .where(*conditions)
            .order_by(distance)
        )

        result = await self.session.execute(stmt)

        return [
            CrimeEventWithDistance(
                event=event,
                distance_m=float(distance_m),
                latitude=float(latitude),
                longitude=float(longitude),
            )
            for event, distance_m, latitude, longitude in result.all()
        ]

    async def get_in_corridor(
        self,
        route_wkt: str,
        buffer_m: float = 3000.0,
    ) -> list[CrimeEvent]:
        """Pobiera zdarzenia znajdujące się w metrycznym buforze trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        stmt = select(CrimeEvent).where(func.ST_Intersects(CrimeEvent.geom, corridor))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())