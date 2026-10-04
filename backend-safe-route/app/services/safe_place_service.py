"""Use cases for retrieving safe places and their distance from a location."""

from typing import TypedDict

from app.enums.safe_place import SafePlaceCategory
from app.models.safe_place import SafePlace
from app.repositories.safe_place_repository import (
    NearbySafePlaceRow,
    SafePlaceCoordinateRow,
    SafePlaceRepository,
)
from app.schemas.safe_place import NearbySafePlaceResponse, SafePlaceResponse


class SafePlaceResponseFields(TypedDict):
    id: int
    category: SafePlaceCategory
    name: str
    opening_hours_raw: str | None
    is_24_7: bool
    latitude: float
    longitude: float


class SafePlaceService:
    """Maps safe-place repository results to public API response models."""

    def __init__(self, repository: SafePlaceRepository) -> None:
        self.repository = repository

    async def get_by_id(self, safe_place_id: int) -> SafePlaceResponse | None:
        row = await self.repository.get_by_id(safe_place_id)
        if row is None:
            return None
        return self._to_response(row)

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
    ) -> list[NearbySafePlaceResponse]:
        rows = await self.repository.get_nearby(
            longitude=longitude,
            latitude=latitude,
            radius_m=radius_m,
        )
        return [self._to_nearby_response(row) for row in rows]

    @staticmethod
    def _base_response(
        safe_place: SafePlace,
        latitude: float,
        longitude: float,
    ) -> SafePlaceResponseFields:
        return {
            "id": safe_place.id,
            "category": safe_place.category,
            "name": safe_place.name,
            "opening_hours_raw": safe_place.opening_hours_raw,
            "is_24_7": safe_place.is_24_7,
            "latitude": latitude,
            "longitude": longitude,
        }

    @classmethod
    def _to_response(cls, row: SafePlaceCoordinateRow) -> SafePlaceResponse:
        safe_place, latitude, longitude = row
        return SafePlaceResponse(
            **cls._base_response(safe_place, latitude, longitude),
        )

    @classmethod
    def _to_nearby_response(cls, row: NearbySafePlaceRow) -> NearbySafePlaceResponse:
        safe_place, distance_m, latitude, longitude = row
        return NearbySafePlaceResponse(
            **cls._base_response(safe_place, latitude, longitude),
            distance_m=distance_m,
        )
