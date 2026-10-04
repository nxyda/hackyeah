from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    Integer,
    func, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import DatabaseBase
from app.enums.report import ReportStatus, ReportCategory
from app.spatial import SpatialValue, WGS84_SRID
if TYPE_CHECKING:
    from app.models.user import User



class Report(DatabaseBase):
    """Bieżące zgłoszenie użytkownika."""

    __tablename__ = "reports"

    __table_args__ = (
        CheckConstraint(
            "confirmations >= 0",
            name="confirmations_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    category: Mapped[ReportCategory] = mapped_column(
        SQLEnum(
            ReportCategory,
            name="report_category",
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(
            ReportStatus,
            name="report_status",
        ),
        nullable=False,
        default=ReportStatus.ACTIVE,
        server_default=ReportStatus.ACTIVE.name,
    )

    confirmations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="reports",
    )