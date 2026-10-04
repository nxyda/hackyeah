from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Double, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import DatabaseBase
from app.enums.crime_event import CrimeEventCategory
from app.spatial import SpatialValue, WGS84_SRID


class CrimeEvent(DatabaseBase):
    """Zdarzenie kryminalne pochodzące z zewnętrznego źródła danych."""

    __tablename__ = "crime_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    category: Mapped[CrimeEventCategory] = mapped_column(
        SQLEnum(
            CrimeEventCategory,
            name="crime_event_category",
        ),
        nullable=False,
    )

    geom: Mapped[SpatialValue] = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=WGS84_SRID,
            spatial_index=True,
        ),
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[float | None] = mapped_column(
        Double,
        nullable=True,
    )