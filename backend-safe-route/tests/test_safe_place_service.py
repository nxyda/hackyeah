"""Tests for mapping safe-place repository rows to API DTOs."""

import asyncio
from types import SimpleNamespace

from app.enums.safe_place import SafePlaceCategory
from app.schemas.safe_place import NearbySafePlaceResponse, SafePlaceResponse
from app.services.safe_place_service import SafePlaceService


class FakeSafePlaceRepository:
    def __init__(self) -> None:
        self.place = SimpleNamespace(
            id=17,
            category=SafePlaceCategory.POLICE,
            name="Central station",
            opening_hours_raw="24/7",
            is_24_7=True,
        )

    async def get_by_id(self, safe_place_id: int):
        if safe_place_id != self.place.id:
            return None
        return self.place, 50.0647, 19.945

    async def get_nearby(self, *, longitude: float, latitude: float, radius_m: float):
        assert (longitude, latitude, radius_m) == (19.945, 50.0647, 1_000)
        return [(self.place, 125.5, 50.0647, 19.945)]


def test_get_by_id_returns_safe_place_dto_with_coordinates() -> None:
    service = SafePlaceService(FakeSafePlaceRepository())

    result = asyncio.run(service.get_by_id(17))

    assert isinstance(result, SafePlaceResponse)
    assert result.model_dump() == {
        "id": 17,
        "category": SafePlaceCategory.POLICE,
        "name": "Central station",
        "opening_hours_raw": "24/7",
        "is_24_7": True,
        "latitude": 50.0647,
        "longitude": 19.945,
    }


def test_get_nearby_returns_distance_dto() -> None:
    service = SafePlaceService(FakeSafePlaceRepository())

    result = asyncio.run(
        service.get_nearby(longitude=19.945, latitude=50.0647, radius_m=1_000)
    )

    assert len(result) == 1
    assert isinstance(result[0], NearbySafePlaceResponse)
    assert result[0].distance_m == 125.5
    assert result[0].latitude == 50.0647
    assert result[0].longitude == 19.945


def test_get_by_id_returns_none_for_missing_place() -> None:
    service = SafePlaceService(FakeSafePlaceRepository())

    assert asyncio.run(service.get_by_id(999)) is None
