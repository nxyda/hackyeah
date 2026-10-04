"""Reusable API schemas for WGS84 spatial data."""

from pydantic import BaseModel, Field


class GeoPointResponse(BaseModel):
    """A point represented as validated WGS84 latitude and longitude."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)