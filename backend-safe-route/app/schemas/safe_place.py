"""API response models for safe places."""

from app.enums.safe_place import SafePlaceCategory
from app.schemas.spatial import GeoPointResponse


class SafePlaceResponse(GeoPointResponse):
    """Public safe-place details with WGS84 coordinates."""

    id: int
    category: SafePlaceCategory
    name: str
    opening_hours_raw: str | None
    is_24_7: bool

class NearbySafePlaceResponse(SafePlaceResponse):
    """Safe-place details augmented with its distance from a search point."""

    distance_m: float
