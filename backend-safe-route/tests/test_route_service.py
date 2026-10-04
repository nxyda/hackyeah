import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from geoalchemy2 import WKTElement
from geoalchemy2.elements import WKBElement
from shapely.geometry import LineString, Point
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2.shape import from_shape

from app.integrations.mapbox_directions_client import MapboxRoute
from app.schemas.route import Coordinate, RouteRequest
from app.scoring.scoring_config import load_scoring_config
from app.services import route_service
from app.services.route_service import RouteService


def test_fallback_segment_has_neutral_missing_data() -> None:
    segment = RouteService._fallback_segment(1200)

    assert segment.length_m == 1200
    assert segment.lit_ratio is None
    assert segment.reports_nearby == 0
    assert segment.is_footway is None


def test_route_distance_projection_uses_local_metric_units() -> None:
    start = RouteService._metric_point(Point(19.945, 50.0647))
    north = RouteService._metric_point(Point(19.945, 50.0657))

    assert start.distance(north) == pytest.approx(111, abs=2)


def test_spatial_values_are_decoded_as_shapely_geometries() -> None:
    point = RouteService._point_geometry(
        WKTElement("POINT(19.945 50.0647)", srid=4326)
    )
    line = RouteService._geometry_coordinates(
        WKTElement("LINESTRING(19.945 50.0647,19.946 50.0647)", srid=4326)
    )

    assert point.x == pytest.approx(19.945)
    assert point.y == pytest.approx(50.0647)
    assert line == ((19.945, 50.0647), (19.946, 50.0647))

    binary_point = from_shape(Point(19.945, 50.0647), srid=4326)
    assert isinstance(binary_point, WKBElement)
    assert RouteService._point_geometry(binary_point).x == pytest.approx(19.945)


def test_route_request_contract_accepts_timezone_aware_departure() -> None:
    request = RouteRequest(
        start={"lat": 50.0614, "lon": 19.9366},
        end={"lat": 50.0543, "lon": 19.9353},
        departure_time=datetime.fromisoformat("2026-10-03T19:20:00+02:00"),
        safety_weight=0.7,
        profile="walking",
    )

    assert request.profile == "walking"
    assert request.departure_time.tzinfo is not None


@pytest.mark.parametrize(
    "coordinates",
    [
        {"lat": -90, "lon": -180},
        {"lat": 90, "lon": 180},
    ],
)
def test_route_coordinate_accepts_geographic_boundaries(
    coordinates: dict[str, int],
) -> None:
    assert Coordinate.model_validate(coordinates).model_dump() == coordinates


@pytest.mark.parametrize(
    "coordinates",
    [
        {"lat": -90.0001, "lon": 0},
        {"lat": 90.0001, "lon": 0},
        {"lat": 0, "lon": -180.0001},
        {"lat": 0, "lon": 180.0001},
    ],
)
def test_route_coordinate_rejects_values_outside_geographic_boundaries(
    coordinates: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        Coordinate.model_validate(coordinates)


def test_database_failure_is_not_returned_as_an_empty_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MapboxStub:
        def get_walking_routes(self, start, end, alternatives):
            return (
                MapboxRoute(
                    route_index=0,
                    geometry=((19.9366, 50.0614), (19.9353, 50.0543)),
                    duration_s=600,
                    distance_m=850,
                ),
            )

        def close(self) -> None:
            pass

    async def fail_database_query(self, route_wkt, buffer_m):
        raise SQLAlchemyError("test database unavailable")

    monkeypatch.setattr(
        route_service,
        "get_settings",
        lambda: SimpleNamespace(
            mapbox_secret_token=SimpleNamespace(
                get_secret_value=lambda: "test-token"
            ),
            routing_corridor_buffer_m=250,
        ),
    )
    monkeypatch.setattr(
        route_service,
        "MapboxDirectionsClient",
        lambda token: MapboxStub(),
    )
    monkeypatch.setattr(
        route_service.RoadSegmentRepository,
        "get_in_corridor",
        fail_database_query,
    )
    request = RouteRequest(
        start={"lat": 50.0614, "lon": 19.9366},
        end={"lat": 50.0543, "lon": 19.9353},
        departure_time=datetime.fromisoformat("2026-10-03T12:00:00+00:00"),
        safety_weight=0.5,
        profile="walking",
    )

    with pytest.raises(SQLAlchemyError, match="test database unavailable"):
        asyncio.run(RouteService(object()).calculate_route(request))


def test_nearby_crime_event_is_added_to_segment_exposure() -> None:
    _, normalization = load_scoring_config()
    segment = SimpleNamespace(
        id=1,
        geom=LineString([(19.936, 50.061), (19.937, 50.061)]),
        length_m=100.0,
        lit_ratio=None,
        is_tunnel=False,
        dist_to_safe_place_m=None,
        is_footway=True,
        surveillance_nearby=None,
    )
    event = SimpleNamespace(
        category="ASSAULT",
        geom=Point(19.9365, 50.06101),
        occurred_at=datetime.fromisoformat("2026-10-01T12:00:00+00:00"),
    )

    graph_segment = RouteService._to_graph_segment(
        segment,
        [event],
        datetime.fromisoformat("2026-10-03T12:00:00+00:00"),
        normalization,
    )

    assert graph_segment.safety.crime_exposure is not None
    assert graph_segment.safety.crime_exposure > 0
