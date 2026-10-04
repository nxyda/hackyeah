"""Repozytorium odczytu i zapisu latarni ulicznych."""

from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.street_lamp import StreetLamp
from app.repositories.base_repository import BaseRepository
from app.spatial import geography_point, metric_route_corridor, point_wkt


class StreetLampRepository(BaseRepository):
    """Operacje bazodanowe dla latarni ulicznych."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, lamp_id: int) -> tuple[StreetLamp, float, float] | None:
        result = await self.session.execute(
            select(
                StreetLamp,
                func.ST_Y(StreetLamp.location).label("latitude"),
                func.ST_X(StreetLamp.location).label("longitude"),
            ).where(StreetLamp.id == lamp_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        lamp, latitude, longitude = row
        return lamp, float(latitude), float(longitude)

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[tuple[StreetLamp, float, float, float]]:
        point = geography_point(longitude, latitude)
        distance = func.ST_Distance(
            StreetLamp.location.cast(Geography),
            point,
        ).label("distance_m")
        result = await self.session.execute(
            select(
                StreetLamp,
                distance,
                func.ST_Y(StreetLamp.location).label("latitude"),
                func.ST_X(StreetLamp.location).label("longitude"),
            )
            .where(
                func.ST_DWithin(
                    StreetLamp.location.cast(Geography),
                    point,
                    radius_m,
                ),
            )
            .order_by(distance, StreetLamp.id)
        )
        return [
            (lamp, float(distance_m), float(lat), float(lon))
            for lamp, distance_m, lat, lon in result.all()
        ]

    async def list_all(self) -> list[tuple[StreetLamp, float, float]]:
        result = await self.session.execute(
            select(
                StreetLamp,
                func.ST_Y(StreetLamp.location).label("latitude"),
                func.ST_X(StreetLamp.location).label("longitude"),
            ).order_by(StreetLamp.id)
        )
        return [
            (lamp, latitude, longitude)
            for lamp, latitude, longitude in result.all()
        ]

    async def get_in_corridor(self, route_wkt: str, buffer_m: float = 3000.0) -> list[StreetLamp]:
        """Pobiera latarnie z metrycznego bufora trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        result = await self.session.execute(
            select(StreetLamp).where(func.ST_Intersects(StreetLamp.location, corridor))
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        osm_id: int,
        latitude: float,
        longitude: float,
    ) -> StreetLamp:
        lamp = StreetLamp(
            osm_id=osm_id,
            location=point_wkt(longitude, latitude),
        )
        self.session.add(lamp)
        await self.session.flush()
        return lamp

    async def delete(self, lamp_id: int) -> bool:
        row = await self.get_by_id(lamp_id)
        if row is None:
            return False
        lamp, _, _ = row
        await self.session.delete(lamp)
        await self.session.flush()
        return True
