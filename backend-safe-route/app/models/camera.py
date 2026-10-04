"""Model kamery monitoringu i jej lokalizacji."""

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import DatabaseBase
from app.spatial import SpatialValue, WGS84_SRID


class Camera(DatabaseBase):
    """Kamera z lokalizacją zapisaną jako punkt WGS84."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    osm_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
    )
    location: Mapped[SpatialValue] = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=WGS84_SRID,
            spatial_index=True,
        ),
        nullable=False,
    )
