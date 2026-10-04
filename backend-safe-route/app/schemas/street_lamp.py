"""Public response models for street lamps."""

from app.schemas.spatial import GeoPointResponse


class StreetLampResponse(GeoPointResponse):
    """Street-lamp details with WGS84 coordinates."""

    id: int
    osm_id: int | None

class NearbyStreetLampResponse(StreetLampResponse):
    """Street-lamp details augmented with distance from a search point."""

    distance_m: float
