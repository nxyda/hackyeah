"""Public response models for historical safety events."""

from datetime import datetime

from app.enums.crime_event import CrimeEventCategory
from app.schemas.spatial import GeoPointResponse


class CrimeEventResponse(GeoPointResponse):
    """Historical crime event with WGS84 coordinates."""

    id: int
    category: CrimeEventCategory
    occurred_at: datetime
    source: str
    severity: float | None


class NearbyCrimeEventResponse(CrimeEventResponse):
    """Crime event augmented with distance from a search point."""

    distance_m: float
