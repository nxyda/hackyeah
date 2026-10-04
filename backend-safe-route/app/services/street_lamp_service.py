"""Use cases for querying street lamps."""

from app.models.street_lamp import StreetLamp
from app.repositories.street_lamp_repository import StreetLampRepository
from app.schemas.street_lamp import NearbyStreetLampResponse, StreetLampResponse


class StreetLampService:
    """Maps street-lamp repository rows to public response models."""

    def __init__(self, repository: StreetLampRepository) -> None:
        self.repository = repository

    async def get_by_id(self, lamp_id: int) -> StreetLampResponse | None:
        row = await self.repository.get_by_id(lamp_id)
        if row is None:
            return None
        lamp, latitude, longitude = row
        return self._to_response(lamp, None, latitude, longitude)

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[NearbyStreetLampResponse]:
        return [
            self._to_response(lamp, distance, lat, lon)
            for lamp, distance, lat, lon in await self.repository.get_nearby(
                longitude=longitude,
                latitude=latitude,
                radius_m=radius_m,
            )
        ]

    @staticmethod
    def _to_response(
        lamp: StreetLamp,
        distance_m: float | None,
        latitude: float | None,
        longitude: float | None,
    ) -> StreetLampResponse | NearbyStreetLampResponse:
        response = {
            "id": lamp.id,
            "osm_id": lamp.osm_id,
            "latitude": latitude,
            "longitude": longitude,
        }
        if distance_m is None:
            return StreetLampResponse(**response)
        return NearbyStreetLampResponse(**response, distance_m=distance_m)
