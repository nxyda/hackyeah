"""Public response models for monitoring cameras."""

from app.schemas.spatial import GeoPointResponse


class CameraResponse(GeoPointResponse):
    """Camera details with WGS84 coordinates."""

    id: int
    osm_id: int | None

class NearbyCameraResponse(CameraResponse):
    """Camera details augmented with distance from a search point."""

    distance_m: float
