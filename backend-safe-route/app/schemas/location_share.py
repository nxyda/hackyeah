"""Request and response DTOs for temporary location sharing."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationShareCreate(BaseModel):
    """Initial location and duration for a new share."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    duration_seconds: int = Field(gt=0, le=86_400)


class LocationUpdate(BaseModel):
    """Latest location reported by the owner."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class LocationShareResponse(BaseModel):
    """Share details visible to its owner."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    lat: float
    lon: float
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class SharedLocationResponse(BaseModel):
    """Read-only current location visible to a user with the code."""

    code: str
    owner_user_id: int
    lat: float
    lon: float
    updated_at: datetime
    expires_at: datetime
