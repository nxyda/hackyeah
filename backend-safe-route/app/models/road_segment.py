from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import DatabaseBase
from app.spatial import SpatialValue, WGS84_SRID


class RoadSegment(DatabaseBase):
    """Segment drogi, chodnika lub ścieżki pochodzący z OSM."""

    __tablename__ = "road_segments"

    __table_args__ = (
        CheckConstraint(
            "length_m > 0",
            name="length_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    osm_way_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
    )

    geom: Mapped[SpatialValue] = mapped_column(
        Geometry(
            geometry_type="LINESTRING",
            srid=WGS84_SRID,
            spatial_index=True,
        ),
        nullable=False,
    )

    length_m: Mapped[float] = mapped_column(
        Double,
        nullable=False,
    )

    road_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_tunnel: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_footway: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    surface: Mapped[str | None] = mapped_column(Text, nullable=True)
    smoothness: Mapped[str | None] = mapped_column(Text, nullable=True)
    incline: Mapped[float | None] = mapped_column(Double, nullable=True)
    lit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    foot: Mapped[str | None] = mapped_column(Text, nullable=True)
    access: Mapped[str | None] = mapped_column(Text, nullable=True)
    crossing: Mapped[str | None] = mapped_column(Text, nullable=True)
    highway: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
