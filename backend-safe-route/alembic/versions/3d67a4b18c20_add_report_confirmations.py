"""add unique report confirmations

Revision ID: 3d67a4b18c20
Revises: 8a6d2e1c4f90
Create Date: 2026-10-03 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d67a4b18c20"
down_revision: Union[str, Sequence[str], None] = "8a6d2e1c4f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_confirmations",
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name=op.f("fk_report_confirmations_report_id_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_confirmations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "report_id",
            "user_id",
            name=op.f("pk_report_confirmations"),
        ),
    )


def downgrade() -> None:
    op.drop_table("report_confirmations")
