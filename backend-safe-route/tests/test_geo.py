import pytest
from geoalchemy2 import WKTElement
from sqlalchemy.dialects import postgresql

from app.spatial import (
    METRIC_SRID,
    WGS84_SRID,
    geography_point,
    metric_route_corridor,
    point_wkt,
)
from app.schemas.route import GeoJSONLineString
from app.schemas.spatial import GeoPointResponse


def test_point_wkt_uses_validated_longitude_latitude_order() -> None:
    point = point_wkt(19.945, 50.0647)

    assert isinstance(point, WKTElement)
    assert point.srid == WGS84_SRID
    assert point.data == "POINT(19.945 50.0647)"


def test_geography_point_is_wgs84_and_keeps_lon_lat_order() -> None:
    compiled = geography_point(19.945, 50.0647).compile(
        dialect=postgresql.dialect()
    )

    assert WGS84_SRID in compiled.params.values()
    assert 19.945 in compiled.params.values()
    assert 50.0647 in compiled.params.values()
    assert "geography" in str(compiled)


@pytest.mark.parametrize(
    ("longitude", "latitude"),
    [(181, 0), (0, -91), (float("nan"), 0)],
)
def test_point_wkt_rejects_invalid_wgs84_coordinates(
    longitude: float,
    latitude: float,
) -> None:
    with pytest.raises(ValueError):
        point_wkt(longitude, latitude)


def test_metric_route_corridor_uses_metric_projection() -> None:
    compiled = metric_route_corridor(
        "LINESTRING(19.945 50.0647,19.946 50.0647)",
        250,
    ).compile(
        dialect=postgresql.dialect()
    )

    assert "ST_Transform" in str(compiled)
    assert "ST_Buffer" in str(compiled)
    assert METRIC_SRID in compiled.params.values()
    assert WGS84_SRID in compiled.params.values()


@pytest.mark.parametrize("buffer_m", [0, -1, float("inf")])
def test_metric_route_corridor_rejects_invalid_buffer(buffer_m: float) -> None:
    with pytest.raises(ValueError):
        metric_route_corridor("LINESTRING(0 0,1 1)", buffer_m)


def test_geo_point_schema_rejects_out_of_range_coordinates() -> None:
    with pytest.raises(ValueError):
        GeoPointResponse(latitude=91, longitude=19)


@pytest.mark.parametrize(
    "coordinates",
    [
        [(19, 50)],
        [(181, 50), (19, 51)],
        [(19, 91), (20, 50)],
        [(19, 50), (20,)],
    ],
)
def test_route_geojson_rejects_invalid_line_coordinates(coordinates) -> None:
    with pytest.raises(ValueError):
        GeoJSONLineString(coordinates=coordinates)
