"""Shared test isolation, network protection, and disposable PostGIS fixtures."""

import asyncio
import ipaddress
import os
import socket
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import TypeVar

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


_TEST_DB_DEFAULTS = {
    "DB_USER": "safe_route_test",
    "DB_PASSWORD": "safe_route_test",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "55432",
    "DB_NAME": "safe_route_test",
    "API_MODE": "mock",
    "MAPBOX_SECRET_TOKEN": "",
    "JWT_SECRET_KEY": "",
    "ADMIN_SESSION_SECRET": "",
    "FACEBOOK_APP_SECRET": "",
}
os.environ.update(_TEST_DB_DEFAULTS)

T = TypeVar("T")


def _is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent accidental calls to real external APIs, including Mapbox."""

    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if not _is_loopback(host):
            raise AssertionError("External network access is disabled in tests")
        return original_getaddrinfo(host, port, *args, **kwargs)

    def guarded_connect(sock, address):
        if not isinstance(address, tuple) or not _is_loopback(address[0]):
            raise AssertionError("External network access is disabled in tests")
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not isinstance(address, tuple) or not _is_loopback(address[0]):
            raise AssertionError("External network access is disabled in tests")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Classify existing isolated tests as unit tests unless marked otherwise."""

    for item in items:
        if not item.get_closest_marker("integration"):
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def run_with_postgis_test_database() -> Callable[[Callable[..., Awaitable[T]]], T]:
    """Run a scenario against a guarded, freshly recreated and seeded test DB."""

    database_url = os.getenv("SAFE_ROUTE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set SAFE_ROUTE_TEST_DATABASE_URL to run the local PostGIS tests"
        )

    url = make_url(database_url)
    if (
        url.drivername != "postgresql+asyncpg"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != "safe_route_test"
        or url.port != 55432
    ):
        raise RuntimeError(
            "Tests require the dedicated local safe_route_test database "
            "at 127.0.0.1:55432"
        )

    def run(scenario: Callable[..., Awaitable[T]]) -> T:
        async def isolated_scenario() -> T:
            from geoalchemy2 import WKTElement

            from app.database.base import DatabaseBase
            from app.enums.crime_event import CrimeEventCategory
            from app.enums.report import ReportCategory, ReportStatus
            from app.enums.safe_place import SafePlaceCategory
            from app.models import (
                Camera,
                CrimeEvent,
                LocationShare,
                Report,
                RoadSegment,
                SafePlace,
                StreetLamp,
                User,
            )

            engine = create_async_engine(database_url, pool_pre_ping=True)
            schema_created = False
            now = datetime.now(timezone.utc)
            try:
                async with engine.begin() as connection:
                    await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                    await connection.run_sync(DatabaseBase.metadata.drop_all)
                    schema_created = True
                    await connection.run_sync(DatabaseBase.metadata.create_all)

                sessions = async_sessionmaker(
                    engine,
                    expire_on_commit=False,
                )
                async with sessions() as session:
                    owner = User(email="route-owner@example.com")
                    reader = User(email="route-reader@example.com")
                    reserved_code_owner = User(
                        email="reserved-code-owner@example.com"
                    )
                    session.add_all([owner, reader, reserved_code_owner])
                    await session.flush()
                    session.add_all(
                        [
                            RoadSegment(
                                osm_way_id=9_000_000_001,
                                geom=WKTElement(
                                    "LINESTRING(19.9366 50.0614, 19.9353 50.0543)",
                                    srid=4326,
                                ),
                                length_m=850,
                                road_type="footway",
                                is_footway=True,
                                is_tunnel=False,
                            ),
                            RoadSegment(
                                osm_way_id=9_000_000_004,
                                geom=WKTElement(
                                    "LINESTRING(19.9366 50.0614, 19.9370 50.0580)",
                                    srid=4326,
                                ),
                                length_m=420,
                                road_type="residential",
                                is_footway=False,
                                is_tunnel=True,
                                surface="asphalt",
                            ),
                            RoadSegment(
                                osm_way_id=9_000_000_005,
                                geom=WKTElement(
                                    "LINESTRING(19.9370 50.0580, 19.9353 50.0543)",
                                    srid=4326,
                                ),
                                length_m=470,
                                road_type="footway",
                                is_footway=True,
                                incline=0.04,
                                crossing="marked",
                            ),
                            CrimeEvent(
                                category=CrimeEventCategory.ASSAULT,
                                geom=WKTElement(
                                    "POINT(19.9360 50.0580)",
                                    srid=4326,
                                ),
                                occurred_at=datetime.fromisoformat(
                                    "2026-10-01T12:00:00+00:00"
                                ),
                                source="test",
                            ),
                            CrimeEvent(
                                category=CrimeEventCategory.ROBBERY,
                                geom=WKTElement(
                                    "POINT(19.9370 50.0580)",
                                    srid=4326,
                                ),
                                occurred_at=now - timedelta(days=1),
                                source="test",
                                severity=0.8,
                            ),
                            StreetLamp(
                                osm_id=9_000_000_002,
                                location=WKTElement(
                                    "POINT(19.9361 50.0580)",
                                    srid=4326,
                                ),
                            ),
                            StreetLamp(
                                osm_id=9_000_000_006,
                                location=WKTElement(
                                    "POINT(19.9370 50.0580)",
                                    srid=4326,
                                ),
                            ),
                            Camera(
                                osm_id=9_000_000_003,
                                location=WKTElement(
                                    "POINT(19.9362 50.0580)",
                                    srid=4326,
                                ),
                            ),
                            Camera(
                                osm_id=9_000_000_007,
                                location=WKTElement(
                                    "POINT(19.9371 50.0580)",
                                    srid=4326,
                                ),
                            ),
                            SafePlace(
                                category=SafePlaceCategory.POLICE,
                                name="Test police station",
                                geom=WKTElement(
                                    "POINT(19.9363 50.0580)",
                                    srid=4326,
                                ),
                                is_24_7=True,
                            ),
                            SafePlace(
                                category=SafePlaceCategory.PHARMACY,
                                name="Test daytime pharmacy",
                                geom=WKTElement(
                                    "POINT(19.9372 50.0580)",
                                    srid=4326,
                                ),
                                opening_hours_raw="Mo-Su 08:00-16:00",
                            ),
                            Report(
                                category=ReportCategory.DANGER,
                                geom=WKTElement(
                                    "POINT(19.9360 50.0580)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(hours=2),
                                expires_at=now + timedelta(days=1),
                                status=ReportStatus.ACTIVE,
                                confirmations=1,
                                user_id=owner.id,
                            ),
                            Report(
                                category=ReportCategory.POOR_LIGHTING,
                                geom=WKTElement(
                                    "POINT(19.9359 50.0580)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(hours=1),
                                expires_at=now + timedelta(days=1),
                                status=ReportStatus.ACTIVE,
                                user_id=reader.id,
                            ),
                            Report(
                                category=ReportCategory.OTHER,
                                geom=WKTElement(
                                    "POINT(19.9361 50.0580)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(days=2),
                                status=ReportStatus.RESOLVED,
                                user_id=owner.id,
                            ),
                            Report(
                                category=ReportCategory.HARASSMENT,
                                geom=WKTElement(
                                    "POINT(19.9362 50.0580)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(days=2),
                                expires_at=now - timedelta(seconds=1),
                                status=ReportStatus.ACTIVE,
                                user_id=reader.id,
                            ),
                            Report(
                                category=ReportCategory.SUSPICIOUS_ACTIVITY,
                                geom=WKTElement(
                                    "POINT(19.9363 50.0580)",
                                    srid=4326,
                                ),
                                created_at=now + timedelta(days=1),
                                expires_at=now + timedelta(days=2),
                                status=ReportStatus.ACTIVE,
                                user_id=reader.id,
                            ),
                            Report(
                                category=ReportCategory.SUSPICIOUS_ACTIVITY,
                                geom=WKTElement(
                                    "POINT(19.9800 50.0800)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(hours=1),
                                status=ReportStatus.ACTIVE,
                                user_id=reader.id,
                            ),
                            LocationShare(
                                owner_user_id=owner.id,
                                code="0000",
                                location=WKTElement(
                                    "POINT(19.9366 50.0614)",
                                    srid=4326,
                                ),
                                created_at=now - timedelta(days=2),
                                updated_at=now - timedelta(days=2),
                                expires_at=now - timedelta(seconds=1),
                            ),
                            LocationShare(
                                owner_user_id=reserved_code_owner.id,
                                code="0001",
                                location=WKTElement(
                                    "POINT(19.9353 50.0543)",
                                    srid=4326,
                                ),
                                expires_at=now + timedelta(hours=1),
                            ),
                        ]
                    )
                    await session.commit()

                return await scenario(sessions)
            finally:
                try:
                    if schema_created:
                        async with engine.begin() as connection:
                            await connection.run_sync(DatabaseBase.metadata.drop_all)
                finally:
                    await engine.dispose()

        return asyncio.run(isolated_scenario())

    return run
