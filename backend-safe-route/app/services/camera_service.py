"""Use cases for querying monitoring cameras."""

from app.repositories.camera_repository import CameraRepository
from app.schemas.camera import CameraResponse, NearbyCameraResponse


class CameraService:
    """Maps camera repository rows to public response models."""

    def __init__(self, repository: CameraRepository) -> None:
        self.repository = repository

    async def get_by_id(self, camera_id: int) -> CameraResponse | None:
        row = await self.repository.get_by_id(camera_id)
        if row is None:
            return None
        camera, latitude, longitude = row
        return CameraResponse(
            id=camera.id,
            osm_id=camera.osm_id,
            latitude=latitude,
            longitude=longitude,
        )

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[NearbyCameraResponse]:
        return [
            NearbyCameraResponse(
                id=camera.id,
                osm_id=camera.osm_id,
                latitude=lat,
                longitude=lon,
                distance_m=distance,
            )
            for camera, distance, lat, lon in await self.repository.get_nearby(
                longitude=longitude,
                latitude=latitude,
                radius_m=radius_m,
            )
        ]
