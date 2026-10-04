"""create users table

Revision ID: 65df00ceb079
Revises:
Create Date: 2026-10-03 15:41:17.160708
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "65df00ceb079"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("users")
