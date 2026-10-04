"""Validation tests for the location-sharing API contract."""

import pytest
from pydantic import ValidationError

from app.schemas.location_share import LocationShareCreate, LocationUpdate


@pytest.mark.parametrize(
    ("lat", "lon"),
    (
        (-90, -180),
        (90, 180),
        (0, 0),
    ),
)
def test_location_share_accepts_valid_coordinate_boundaries(lat: float, lon: float) -> None:
    request = LocationShareCreate(lat=lat, lon=lon, duration_seconds=86_400)
    update = LocationUpdate(lat=lat, lon=lon)

    assert (request.lat, request.lon) == (lat, lon)
    assert (update.lat, update.lon) == (lat, lon)


@pytest.mark.parametrize(
    ("lat", "lon"),
    (
        (-90.01, 0),
        (90.01, 0),
        (0, -180.01),
        (0, 180.01),
    ),
)
def test_location_schemas_reject_out_of_range_coordinates(lat: float, lon: float) -> None:
    with pytest.raises(ValidationError):
        LocationUpdate(lat=lat, lon=lon)


@pytest.mark.parametrize("duration_seconds", (0, -1, 86_401))
def test_location_share_rejects_invalid_duration(duration_seconds: int) -> None:
    with pytest.raises(ValidationError):
        LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=duration_seconds)
