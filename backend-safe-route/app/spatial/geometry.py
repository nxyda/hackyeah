"""Shared spatial conventions and PostGIS geometry helpers."""

from math import isfinite

from geoalchemy2 import Geography, WKTElement
from geoalchemy2.elements import WKBElement
from sqlalchemy import cast, func

WGS84_SRID = 4326
METRIC_SRID = 2180
SpatialValue = WKBElement | WKTElement


def point_wkt(longitude: float, latitude: float) -> WKTElement:
    """Build a WGS84 point in the required longitude/latitude axis order."""
    if (
        not isfinite(longitude)
        or not isfinite(latitude)
        or not -180 <= longitude <= 180
        or not -90 <= latitude <= 90
    ):
        raise ValueError("coordinates must be valid WGS84 longitude and latitude")
    return WKTElement(
        f"POINT({longitude} {latitude})",
        srid=WGS84_SRID,
    )


def geography_point(longitude: float, latitude: float):
    """Create a WGS84 point explicitly typed for meter-based geography queries."""
    if (
        not isfinite(longitude)
        or not isfinite(latitude)
        or not -180 <= longitude <= 180
        or not -90 <= latitude <= 90
    ):
        raise ValueError("coordinates must be valid WGS84 longitude and latitude")
    return cast(
        func.ST_SetSRID(
            func.ST_MakePoint(longitude, latitude),
            WGS84_SRID,
        ),
        Geography(srid=WGS84_SRID),
    )


def metric_route_corridor(route_wkt: str, buffer_m: float):
    """Create a metric route buffer in Poland's national projected CRS."""
    if not route_wkt.strip():
        raise ValueError("route_wkt must not be empty")
    if not isfinite(buffer_m) or buffer_m <= 0:
        raise ValueError("buffer_m must be positive and finite")

    route = func.ST_GeomFromText(route_wkt, WGS84_SRID)
    metric_route = func.ST_Transform(route, METRIC_SRID)
    corridor = func.ST_Buffer(metric_route, buffer_m)
    return func.ST_Transform(corridor, WGS84_SRID)
