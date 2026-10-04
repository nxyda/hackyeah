"""Repozytorium odczytu i zapisu kamer."""

from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.repositories.base_repository import BaseRepository
from app.spatial import geography_point, metric_route_corridor, point_wkt


class CameraRepository(BaseRepository):
    """Operacje bazodanowe dla kamer."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, camera_id: int) -> tuple[Camera, float, float] | None:
        result = await self.session.execute(
            select(
                Camera,
                func.ST_Y(Camera.location).label("latitude"),
                func.ST_X(Camera.location).label("longitude"),
            ).where(Camera.id == camera_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        camera, latitude, longitude = row
        return camera, float(latitude), float(longitude)

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[tuple[Camera, float, float, float]]:
        point = geography_point(longitude, latitude)
        distance = func.ST_Distance(
            Camera.location.cast(Geography),
            point,
        ).label("distance_m")
        result = await self.session.execute(
            select(
                Camera,
                distance,
                func.ST_Y(Camera.location).label("latitude"),
                func.ST_X(Camera.location).label("longitude"),
            )
            .where(
                func.ST_DWithin(
                    Camera.location.cast(Geography),
                    point,
                    radius_m,
                ),
            )
            .order_by(distance, Camera.id)
        )
        return [
            (camera, float(distance_m), float(lat), float(lon))
            for camera, distance_m, lat, lon in result.all()
        ]

    async def list_all(self) -> list[tuple[Camera, float, float]]:
        result = await self.session.execute(
            select(
                Camera,
                func.ST_Y(Camera.location).label("latitude"),
                func.ST_X(Camera.location).label("longitude"),
            ).order_by(Camera.id)
        )
        return [
            (camera, latitude, longitude)
            for camera, latitude, longitude in result.all()
        ]

    async def get_in_corridor(self, route_wkt: str, buffer_m: float = 3000.0) -> list[Camera]:
        """Pobiera kamery z metrycznego bufora trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        result = await self.session.execute(
            select(Camera).where(func.ST_Intersects(Camera.location, corridor))
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        osm_id: int,
        latitude: float,
        longitude: float,
    ) -> Camera:
        camera = Camera(
            osm_id=osm_id,
            location=point_wkt(longitude, latitude),
        )
        self.session.add(camera)
        await self.session.flush()
        return camera

    async def delete(self, camera_id: int) -> bool:
        row = await self.get_by_id(camera_id)
        if row is None:
            return False
        camera, _, _ = row
        await self.session.delete(camera)
        await self.session.flush()
        return True
