"""Tests for lamp persistence and dynamically computed road-segment DTOs."""

import asyncio
from types import SimpleNamespace

from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy.dialects import postgresql
from sqlalchemy import BigInteger

from app.models.camera import Camera
from app.models.safe_place import SafePlace
from app.models.street_lamp import StreetLamp
from app.models.road_segment import RoadSegment
from app.models.safe_place import SafePlace
from app.repositories.road_segment_repository import RoadSegmentRepository
from app.repositories.safe_place_repository import SafePlaceRepository
from app.repositories.street_lamp_repository import StreetLampRepository


def test_safe_place_osm_id_is_optional_and_unique() -> None:
    column = SafePlace.__table__.columns["osm_id"]
    unique_constraint = next(
        constraint
        for constraint in SafePlace.__table__.constraints
        if constraint.name == "uq_safe_places_osm_id"
    )

    assert column.nullable
    assert [column.name for column in unique_constraint.columns] == ["osm_id"]


def test_road_segment_osm_way_id_is_unique() -> None:
    unique_constraint = next(
        constraint
        for constraint in RoadSegment.__table__.constraints
        if constraint.name == "uq_road_segments_osm_way_id"
    )

    assert [column.name for column in unique_constraint.columns] == ["osm_way_id"]


def test_camera_and_lamp_osm_ids_are_bigint_and_unique() -> None:
    for model in (Camera, StreetLamp):
        column = model.__table__.c.osm_id
        assert isinstance(column.type, BigInteger)
        assert column.unique


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.rows

    def one_or_none(self):
        return self.rows


class FakeSession:
    def __init__(self, result=None):
        self.result = result
        self.added = []
        self.deleted = []
        self.executed = []
        self.flushed = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return FakeResult(self.result)

    def add(self, instance):
        self.added.append(instance)

    async def flush(self):
        self.flushed += 1

    async def delete(self, instance):
        self.deleted.append(instance)


def test_street_lamp_repository_creates_point_in_wgs84() -> None:
    session = FakeSession()
    repository = StreetLampRepository(session)

    lamp = asyncio.run(
        repository.create(osm_id=9_000_000_001, latitude=50.0647, longitude=19.945)
    )

    assert isinstance(lamp, StreetLamp)
    assert lamp.osm_id == 9_000_000_001
    assert to_shape(lamp.location).wkt == "POINT (19.945 50.0647)"
    assert session.added == [lamp]
    assert session.flushed == 1


def test_road_segment_repository_returns_dynamic_safe_place_distance() -> None:
    segment = SimpleNamespace(
        id=12,
        osm_way_id=9001,
        geom=WKTElement("LINESTRING(19.94 50.06, 19.95 50.07)", srid=4326),
        length_m=150.5,
        road_type="footway",
        is_tunnel=False,
        is_footway=True,
        source="osm",
        source_updated_at=None,
    )
    session = FakeSession([(segment, 42.75)])
    repository = RoadSegmentRepository(session)

    result = asyncio.run(repository.list_with_safety_data())

    assert len(result) == 1
    assert result[0].id == 12
    assert result[0].geometry_wkt == "LINESTRING (19.94 50.06, 19.95 50.07)"
    assert result[0].dist_to_safe_place_m == 42.75
    sql = str(session.executed[0].compile(dialect=postgresql.dialect()))
    assert "ST_Distance" in sql
    assert "geography" in sql
    assert "FROM safe_places" in sql


def test_road_segment_no_longer_persists_derived_safety_fields() -> None:
    assert {"lit_ratio", "surveillance_nearby", "dist_to_safe_place_m"}.isdisjoint(
        RoadSegment.__table__.columns.keys()
    )


def test_road_segment_safety_query_is_empty_for_no_requested_ids() -> None:
    session = FakeSession()
    repository = RoadSegmentRepository(session)

    result = asyncio.run(repository.get_safety_data_by_ids([]))

    assert result == []
    assert session.executed == []


def test_safe_place_repository_returns_entity_and_coordinates() -> None:
    safe_place = SimpleNamespace(id=3)
    session = FakeSession((safe_place, 50.0647, 19.945))
    repository = SafePlaceRepository(session)

    result = asyncio.run(repository.get_by_id(3))

    assert result == (safe_place, 50.0647, 19.945)


def test_safe_place_repository_nearby_returns_internal_rows() -> None:
    safe_place = SimpleNamespace(id=3)
    session = FakeSession([(safe_place, 125.5, 50.0647, 19.945)])
    repository = SafePlaceRepository(session)

    result = asyncio.run(
        repository.get_nearby(longitude=19.945, latitude=50.0647, radius_m=500)
    )

    assert result == [(safe_place, 125.5, 50.0647, 19.945)]
