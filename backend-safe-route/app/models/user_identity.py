"""Zewnętrzne tożsamości OAuth powiązane z kontami użytkowników."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import DatabaseBase
from app.enums.oauth_provider import OAuthProvider
from app.models.user import User


class UserIdentity(DatabaseBase):
    """Powiązanie konta aplikacji z identyfikatorem Google lub Facebooka."""

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_user_identities_provider_user_id",
        ),
        CheckConstraint(
            "provider IN ('google', 'facebook')",
            name="provider_supported",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[OAuthProvider] = mapped_column(
        SQLEnum(
            OAuthProvider,
            name="oauth_provider",
            native_enum=False,
            create_constraint=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    user: Mapped[User] = relationship(back_populates="identities")
