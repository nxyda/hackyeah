"""Kompletne modele Pydantic kontraktu planowania trasy."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """Współrzędne geograficzne punktu."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class GeoJSONLineString(BaseModel):
    """GeoJSON LineString zapisany jako współrzędne longitude, latitude."""

    type: Literal["LineString"] = "LineString"
    coordinates: list[
        tuple[
            Annotated[float, Field(ge=-180, le=180)],
            Annotated[float, Field(ge=-90, le=90)],
        ]
    ] = Field(min_length=2)


class RouteSegment(BaseModel):
    """Segment trasy z geometrią i poziomem ryzyka."""

    geometry: GeoJSONLineString
    risk_level: float = Field(ge=0, le=100)


class RouteComponents(BaseModel):
    """Składowe wyniku bezpieczeństwa trasy."""

    lit_ratio: float | None = Field(default=None, ge=0, le=1)
    reports_nearby: int = Field(ge=0)
    reports_impact: float = Field(default=0, ge=0)
    crime_exposure: float | None = Field(default=None, ge=0)
    tunnel_m: float = Field(ge=0)
    safe_places_nearby: int = Field(ge=0)
    cameras_nearby: int = Field(default=0, ge=0)
    surface_score: float | None = Field(default=None, ge=0, le=1)
    incline_score: float | None = Field(default=None, ge=0, le=1)
    crossing_score: float | None = Field(default=None, ge=0, le=1)
    road_type_score: float | None = Field(default=None, ge=0, le=1)
    stairs_score: float | None = Field(default=None, ge=0, le=1)
    access_score: float | None = Field(default=None, ge=0, le=1)


class RouteOption(BaseModel):
    """Pojedyncza alternatywa trasy."""

    geometry: GeoJSONLineString
    duration_s: float = Field(ge=0)
    distance_m: float = Field(ge=0)
    safety_score: float = Field(ge=0, le=100)
    components: RouteComponents
    segments: list[RouteSegment]
    explanation: str


class RouteMeta(BaseModel):
    """Metadane pochodzenia i pokrycia danych."""

    mode: Literal["mock", "live"]
    version: str
    data_coverage: str
    route_source: str | None = None


class RouteRequest(BaseModel):
    """Żądanie wyznaczenia trasy."""

    start: Coordinate
    end: Coordinate
    departure_time: datetime
    safety_weight: float = Field(ge=0, le=1)
    profile: Literal["walking"] = "walking"


class RouteResponse(BaseModel):
    """Odpowiedź z trasą najszybszą, najbezpieczniejszą i opcjami."""

    fastest: RouteOption
    safest: RouteOption
    alternatives: list[RouteOption] = Field(default_factory=list)
    meta: RouteMeta


# TODO: Uzgodnić z klientem dokładną semantykę risk_level i data_coverage.
