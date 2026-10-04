from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import DatabaseBase
from app.enums.safe_place import SafePlaceCategory
from app.spatial import SpatialValue, WGS84_SRID


class SafePlace(DatabaseBase):
    """Bezpieczne miejsce dostępne w systemie."""

    __tablename__ = "safe_places"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    osm_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
    )

    category: Mapped[SafePlaceCategory] = mapped_column(
        SQLEnum(SafePlaceCategory, name="safe_place_category"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        Text,
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

    opening_hours_raw: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_24_7: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    source: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
