"""DTO segmentu drogi wzbogaconego o odległość liczoną dynamicznie."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoadSegmentDTO(BaseModel):
    """Dane segmentu potrzebne klientom/scoringowi, bez wartości cache'owanych."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    osm_way_id: int
    geometry_wkt: str
    length_m: float
    road_type: str
    is_tunnel: bool
    is_footway: bool | None
    source: str | None
    source_updated_at: datetime | None
    dist_to_safe_place_m: float | None
