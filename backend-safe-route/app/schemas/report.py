"""Schematy API dla zgłoszeń zagrożeń na trasie."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums.report import ReportCategory, ReportStatus


class ReportCreate(BaseModel):
    """Żądanie utworzenia zgłoszenia."""

    category: ReportCategory
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ReportUpdate(BaseModel):
    """Pola zgłoszenia, które właściciel może zmienić."""

    category: ReportCategory | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_changes(self) -> "ReportUpdate":
        if self.category is None and self.lat is None:
            raise ValueError("At least one report field must be provided")
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class ReportResponse(BaseModel):
    """Zgłoszenie zwracane przez API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: ReportCategory
    lat: float
    lon: float
    created_at: datetime
    expires_at: datetime | None
    status: ReportStatus
    confirmations: int
