"""Persistence operations for temporary location shares."""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location_share import LocationShare
from app.repositories.base_repository import BaseRepository
from app.spatial import point_wkt


LocationShareRow = tuple[LocationShare, float, float]


class LocationShareRepository(BaseRepository):
    """Reads and updates location shares without exposing write access to readers."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def lock_code_allocation(self, now: datetime) -> set[str]:
        """Serializes code allocation and frees codes from expired/revoked shares."""

        await self.session.execute(select(func.pg_advisory_xact_lock(724_019_383_551)))
        await self.session.execute(
            update(LocationShare)
            .where(
                LocationShare.code.is_not(None),
                (LocationShare.expires_at <= now) | LocationShare.revoked_at.is_not(None),
            )
            .values(code=None)
        )
        result = await self.session.execute(
            select(LocationShare.code).where(LocationShare.code.is_not(None))
        )
        return set(result.scalars().all())

    async def get_active_for_owner(
        self,
        owner_user_id: int,
        now: datetime,
    ) -> LocationShareRow | None:
        result = await self.session.execute(
            self._location_query().where(
                LocationShare.owner_user_id == owner_user_id,
                LocationShare.code.is_not(None),
                LocationShare.revoked_at.is_(None),
                LocationShare.expires_at > now,
            )
        )
        return result.one_or_none()

    async def get_active_by_code(self, code: str, now: datetime) -> LocationShareRow | None:
        result = await self.session.execute(
            self._location_query().where(
                LocationShare.code == code,
                LocationShare.revoked_at.is_(None),
                LocationShare.expires_at > now,
            )
        )
        return result.one_or_none()

    async def create(
        self,
        *,
        owner_user_id: int,
        code: str,
        latitude: float,
        longitude: float,
        expires_at: datetime,
    ) -> LocationShare:
        share = LocationShare(
            owner_user_id=owner_user_id,
            code=code,
            location=point_wkt(longitude, latitude),
            expires_at=expires_at,
        )
        self.session.add(share)
        await self.session.flush()
        return share

    async def update_location(
        self,
        *,
        owner_user_id: int,
        latitude: float,
        longitude: float,
        now: datetime,
    ) -> bool:
        result = await self.session.execute(
            update(LocationShare)
            .where(
                LocationShare.owner_user_id == owner_user_id,
                LocationShare.code.is_not(None),
                LocationShare.revoked_at.is_(None),
                LocationShare.expires_at > now,
            )
            .values(
                location=point_wkt(longitude, latitude),
                updated_at=now,
            )
        )
        return result.rowcount > 0

    async def revoke_for_owner(self, owner_user_id: int, now: datetime) -> bool:
        result = await self.session.execute(
            update(LocationShare)
            .where(
                LocationShare.owner_user_id == owner_user_id,
                LocationShare.code.is_not(None),
                LocationShare.revoked_at.is_(None),
            )
            .values(code=None, revoked_at=now)
        )
        return result.rowcount > 0

    @staticmethod
    def _location_query():
        return select(
            LocationShare,
            func.ST_Y(LocationShare.location).label("latitude"),
            func.ST_X(LocationShare.location).label("longitude"),
        )
