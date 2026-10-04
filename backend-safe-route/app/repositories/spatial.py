"""Repository DTOs for spatial-query results."""

from dataclasses import dataclass

from app.models.crime_event import CrimeEvent
from app.models.safe_place import SafePlace


@dataclass(slots=True)
class SafePlaceWithDistance:
    safe_place: SafePlace
    distance_m: float


@dataclass(slots=True)
class CrimeEventWithDistance:
    event: CrimeEvent
    distance_m: float
    latitude: float
    longitude: float
