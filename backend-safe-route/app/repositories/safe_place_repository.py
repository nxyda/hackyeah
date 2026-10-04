from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safe_place import SafePlace
from app.repositories.base_repository import BaseRepository
from app.repositories.spatial import SafePlaceWithDistance
from app.spatial import geography_point, metric_route_corridor


SafePlaceCoordinateRow = tuple[SafePlace, float, float]
NearbySafePlaceRow = tuple[SafePlace, float, float, float]


class SafePlaceRepository(BaseRepository):
    """Repozytorium bezpiecznych miejsc."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(
        self,
        safe_place_id: int,
    ) -> SafePlaceCoordinateRow | None:
        result = await self.session.execute(
            select(
                SafePlace,
                func.ST_Y(SafePlace.geom).label("latitude"),
                func.ST_X(SafePlace.geom).label("longitude"),
            ).where(SafePlace.id == safe_place_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        safe_place, latitude, longitude = row
        return safe_place, float(latitude), float(longitude)

    async def get_nearest(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float | None = None,
    ) -> SafePlaceWithDistance | None:
        point = geography_point(longitude, latitude)

        distance = func.ST_Distance(
            SafePlace.geom.cast(Geography),
            point,
        ).label("distance_m")

        stmt = select(
            SafePlace,
            distance,
        )

        if radius_m is not None:
            stmt = stmt.where(
                func.ST_DWithin(
                    SafePlace.geom.cast(Geography),
                    point,
                    radius_m,
                ),
            )

        stmt = stmt.order_by(distance).limit(1)

        result = await self.session.execute(stmt)

        row = result.first()

        if row is None:
            return None

        safe_place, distance_m = row

        return SafePlaceWithDistance(
            safe_place=safe_place,
            distance_m=float(distance_m),
        )

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[NearbySafePlaceRow]:
        point = geography_point(longitude, latitude)

        distance = func.ST_Distance(
            SafePlace.geom.cast(Geography),
            point,
        ).label("distance_m")

        latitude_column = func.ST_Y(SafePlace.geom).label("latitude")
        longitude_column = func.ST_X(SafePlace.geom).label("longitude")

        stmt = (
            select(
                SafePlace,
                distance,
                latitude_column,
                longitude_column,
            )
            .where(
                func.ST_DWithin(
                    SafePlace.geom.cast(Geography),
                    point,
                    radius_m,
                ),
            )
            .order_by(distance)
        )

        result = await self.session.execute(stmt)

        return [
            (safe_place, float(distance_m), float(latitude), float(longitude))
            for safe_place, distance_m, latitude, longitude in result.all()
        ]

    async def get_in_corridor(
        self,
        route_wkt: str,
        buffer_m: float = 3000.0,
    ) -> list[SafePlace]:
        """Pobiera bezpieczne miejsca z metrycznego bufora trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        result = await self.session.execute(
            select(SafePlace).where(func.ST_Intersects(SafePlace.geom, corridor))
        )
        return list(result.scalars().all())
