"""Potwierdzenia zgłoszeń z unikalnym wpisem na użytkownika i zgłoszenie."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import DatabaseBase


class ReportConfirmation(DatabaseBase):
    """Zapobiega wielokrotnemu potwierdzeniu zgłoszenia przez to samo konto."""

    __tablename__ = "report_confirmations"

    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
