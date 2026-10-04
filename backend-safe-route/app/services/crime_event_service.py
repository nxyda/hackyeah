"""Use cases for querying historical crime events."""

from datetime import datetime

from app.repositories.crime_event_repository import CrimeEventRepository
from app.schemas.crime_event import CrimeEventResponse, NearbyCrimeEventResponse


class CrimeEventService:
    """Maps crime-event repository rows to public response models."""

    def __init__(self, repository: CrimeEventRepository) -> None:
        self.repository = repository

    async def get_by_id(self, event_id: int) -> CrimeEventResponse | None:
        row = await self.repository.get_by_id(event_id)
        if row is None:
            return None
        event, latitude, longitude = row
        return CrimeEventResponse(
            id=event.id,
            category=event.category,
            latitude=latitude,
            longitude=longitude,
            occurred_at=event.occurred_at,
            source=event.source,
            severity=event.severity,
        )

    async def get_nearby(
        self,
        *,
        longitude: float,
        latitude: float,
        radius_m: float,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[NearbyCrimeEventResponse]:
        rows = await self.repository.get_nearby(
            longitude=longitude,
            latitude=latitude,
            radius_m=radius_m,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
        return [
            NearbyCrimeEventResponse(
                id=row.event.id,
                category=row.event.category,
                latitude=row.latitude,
                longitude=row.longitude,
                occurred_at=row.event.occurred_at,
                source=row.event.source,
                severity=row.event.severity,
                distance_m=row.distance_m,
            )
            for row in rows
        ]
