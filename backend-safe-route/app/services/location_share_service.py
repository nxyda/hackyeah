"""Use cases for creating and consuming temporary location shares."""

import secrets
from datetime import datetime, timedelta, timezone

from app.models.location_share import LocationShare
from app.repositories.location_share_repository import (
    LocationShareRepository,
    LocationShareRow,
)
from app.schemas.location_share import (
    LocationShareCreate,
    LocationShareResponse,
    LocationUpdate,
    SharedLocationResponse,
)


class LocationShareNotFoundError(Exception):
    """No active share exists for the requested owner or code."""


class ActiveLocationShareExistsError(Exception):
    """The owner already has an active location share."""


class LocationShareCodeCapacityError(Exception):
    """No four-digit code is currently available."""


class LocationShareService:
    """Coordinates current-location updates and read-only code-based access."""

    def __init__(self, repository: LocationShareRepository) -> None:
        self.repository = repository

    async def create(
        self,
        owner_user_id: int,
        request: LocationShareCreate,
    ) -> LocationShareResponse:
        now = datetime.now(timezone.utc)
        occupied_codes = await self.repository.lock_code_allocation(now)
        if await self.repository.get_active_for_owner(owner_user_id, now) is not None:
            raise ActiveLocationShareExistsError

        available_codes = [
            f"{value:04d}"
            for value in range(10_000)
            if f"{value:04d}" not in occupied_codes
        ]
        if not available_codes:
            raise LocationShareCodeCapacityError

        code = secrets.choice(available_codes)
        share = await self.repository.create(
            owner_user_id=owner_user_id,
            code=code,
            latitude=request.lat,
            longitude=request.lon,
            expires_at=now + timedelta(seconds=request.duration_seconds),
        )
        await self.repository.session.commit()
        row = await self.repository.get_active_by_code(code, now)
        if row is None:
            raise RuntimeError("Created location share could not be retrieved")
        return self._to_owner_response(row)

    async def get_current(self, owner_user_id: int) -> LocationShareResponse:
        row = await self.repository.get_active_for_owner(
            owner_user_id,
            datetime.now(timezone.utc),
        )
        if row is None:
            raise LocationShareNotFoundError
        return self._to_owner_response(row)

    async def update_location(
        self,
        owner_user_id: int,
        request: LocationUpdate,
    ) -> LocationShareResponse:
        now = datetime.now(timezone.utc)
        row = await self.repository.get_active_for_owner(owner_user_id, now)
        if row is None:
            raise LocationShareNotFoundError
        share, latitude, longitude = row
        if latitude != request.lat or longitude != request.lon:
            updated = await self.repository.update_location(
                owner_user_id=owner_user_id,
                latitude=request.lat,
                longitude=request.lon,
                now=now,
            )
            if not updated:
                raise LocationShareNotFoundError
            await self.repository.session.commit()
            refreshed = await self.repository.get_active_for_owner(owner_user_id, now)
            if refreshed is None:
                raise LocationShareNotFoundError
            row = refreshed
        return self._to_owner_response(row)

    async def get_shared_location(
        self,
        reader_user_id: int,
        code: str,
    ) -> SharedLocationResponse:
        row = await self.repository.get_active_by_code(code, datetime.now(timezone.utc))
        if row is None or row[0].owner_user_id == reader_user_id:
            raise LocationShareNotFoundError
        share, latitude, longitude = row
        return SharedLocationResponse(
            code=share.code,
            owner_user_id=share.owner_user_id,
            lat=latitude,
            lon=longitude,
            updated_at=share.updated_at,
            expires_at=share.expires_at,
        )

    async def revoke(self, owner_user_id: int) -> None:
        if not await self.repository.revoke_for_owner(
            owner_user_id,
            datetime.now(timezone.utc),
        ):
            raise LocationShareNotFoundError
        await self.repository.session.commit()

    @staticmethod
    def _to_owner_response(row: LocationShareRow) -> LocationShareResponse:
        share, latitude, longitude = row
        return LocationShareResponse(
            code=share.code,
            lat=latitude,
            lon=longitude,
            created_at=share.created_at,
            updated_at=share.updated_at,
            expires_at=share.expires_at,
        )
