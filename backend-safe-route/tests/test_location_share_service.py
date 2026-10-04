import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.location_share import LocationShareCreate, LocationUpdate
from app.services.location_share_service import (
    ActiveLocationShareExistsError,
    LocationShareCodeCapacityError,
    LocationShareNotFoundError,
    LocationShareService,
)


class FakeLocationShareRepository:
    def __init__(self) -> None:
        self.session = SimpleNamespace(commit=self._commit)
        self.share = None
        self.commits = 0
        self.location_updates = 0
        self.revoked = False
        self.occupied_codes: set[str] = set()

    async def _commit(self) -> None:
        self.commits += 1

    async def lock_code_allocation(self, now: datetime) -> set[str]:
        return self.occupied_codes

    async def get_active_for_owner(self, owner_user_id: int, now: datetime):
        if (
            self.share is None
            or self.share.owner_user_id != owner_user_id
            or self.share.revoked_at is not None
            or self.share.expires_at <= now
        ):
            return None
        return self._row()

    async def get_active_by_code(self, code: str, now: datetime):
        if (
            self.share is None
            or self.share.code != code
            or self.share.revoked_at is not None
            or self.share.expires_at <= now
        ):
            return None
        return self._row()

    async def create(
        self,
        *,
        owner_user_id: int,
        code: str,
        latitude: float,
        longitude: float,
        expires_at: datetime,
    ):
        now = datetime.now(timezone.utc)
        self.share = SimpleNamespace(
            owner_user_id=owner_user_id,
            code=code,
            lat=latitude,
            lon=longitude,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        return self.share

    async def update_location(
        self,
        *,
        owner_user_id: int,
        latitude: float,
        longitude: float,
        now: datetime,
    ) -> bool:
        if (
            self.share is None
            or self.share.owner_user_id != owner_user_id
            or self.share.revoked_at is not None
            or self.share.expires_at <= now
        ):
            return False
        self.share.lat = latitude
        self.share.lon = longitude
        self.share.updated_at = now
        self.location_updates += 1
        return True

    async def revoke_for_owner(self, owner_user_id: int, now: datetime) -> bool:
        if (
            self.share is None
            or self.share.owner_user_id != owner_user_id
            or self.share.code is None
            or self.share.revoked_at is not None
        ):
            return False
        self.share.code = None
        self.share.revoked_at = now
        self.revoked = True
        return True

    def _row(self):
        return self.share, self.share.lat, self.share.lon


def test_create_generates_four_digit_code_and_expiry() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)

    response = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    assert len(response.code) == 4
    assert response.code.isdigit()
    assert response.lat == 50.06
    assert response.lon == 19.94
    assert response.expires_at - response.created_at >= timedelta(seconds=299)
    assert repository.commits == 1


def test_owner_can_only_have_one_active_share() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    request = LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300)
    asyncio.run(service.create(12, request))

    with pytest.raises(ActiveLocationShareExistsError):
        asyncio.run(service.create(12, request))


def test_location_updates_only_write_when_coordinates_change() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )
    original_code = repository.share.code

    unchanged = asyncio.run(
        service.update_location(12, LocationUpdate(lat=50.06, lon=19.94))
    )
    updated = asyncio.run(
        service.update_location(12, LocationUpdate(lat=50.07, lon=19.95))
    )

    assert unchanged.code == original_code
    assert updated.code == original_code
    assert updated.lat == 50.07
    assert updated.lon == 19.95
    assert repository.location_updates == 1


def test_code_reader_gets_latest_location_but_owner_is_not_a_reader() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )
    asyncio.run(service.update_location(12, LocationUpdate(lat=50.07, lon=19.95)))

    shared = asyncio.run(service.get_shared_location(13, created.code))

    assert shared.owner_user_id == 12
    assert (shared.lat, shared.lon) == (50.07, 19.95)
    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.get_shared_location(12, created.code))


def test_revoked_or_expired_share_is_not_readable() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    asyncio.run(service.revoke(12))

    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.get_shared_location(13, created.code))


def test_create_avoids_codes_already_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FakeLocationShareRepository()
    repository.occupied_codes = {"0000", "0001"}
    service = LocationShareService(repository)

    def choose(available_codes: list[str]) -> str:
        assert "0000" not in available_codes
        assert "0001" not in available_codes
        return available_codes[0]

    monkeypatch.setattr("app.services.location_share_service.secrets.choice", choose)
    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    assert created.code not in repository.occupied_codes


def test_create_fails_when_all_codes_are_occupied() -> None:
    repository = FakeLocationShareRepository()
    repository.occupied_codes = {f"{value:04d}" for value in range(10_000)}
    service = LocationShareService(repository)

    with pytest.raises(LocationShareCodeCapacityError):
        asyncio.run(
            service.create(
                12,
                LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
            )
        )

    assert repository.commits == 0


def test_owner_can_get_current_share_and_missing_share_is_not_found() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)

    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.get_current(12))

    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    assert asyncio.run(service.get_current(12)) == created
    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.get_current(13))


def test_location_update_rejects_missing_or_expired_share() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    request = LocationUpdate(lat=50.07, lon=19.95)

    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.update_location(12, request))

    asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )
    repository.share.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.update_location(12, request))

    assert repository.commits == 1
    assert repository.location_updates == 0


def test_revoke_is_owner_scoped_and_commits_once() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.revoke(13))
    assert repository.commits == 1

    asyncio.run(service.revoke(12))

    assert repository.revoked
    assert repository.share.code is None
    assert repository.commits == 2
    with pytest.raises(LocationShareNotFoundError):
        asyncio.run(service.get_shared_location(13, created.code))


def test_location_update_without_changes_does_not_commit() -> None:
    repository = FakeLocationShareRepository()
    service = LocationShareService(repository)
    created = asyncio.run(
        service.create(
            12,
            LocationShareCreate(lat=50.06, lon=19.94, duration_seconds=300),
        )
    )

    unchanged = asyncio.run(
        service.update_location(12, LocationUpdate(lat=created.lat, lon=created.lon))
    )

    assert unchanged == created
    assert repository.commits == 1
    assert repository.location_updates == 0


def test_code_allocation_database_failure_does_not_create_a_share() -> None:
    repository = FakeLocationShareRepository()

    async def fail_lock(now: datetime) -> set[str]:
        raise SQLAlchemyError("share database unavailable")

    repository.lock_code_allocation = fail_lock

    with pytest.raises(SQLAlchemyError, match="share database unavailable"):
        asyncio.run(
            LocationShareService(repository).create(
                12,
                LocationShareCreate(
                    lat=50.06,
                    lon=19.94,
                    duration_seconds=300,
                ),
            )
        )

    assert repository.share is None
    assert repository.commits == 0
