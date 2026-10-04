"""add temporary location shares

Revision ID: 3be8c1a72d94
Revises: c84f19a62d37
Create Date: 2026-10-03 22:55:00.000000
"""

from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


revision: str = "3be8c1a72d94"
down_revision: Union[str, Sequence[str], None] = "c84f19a62d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_shares",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=4), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_location_shares_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_shares")),
        sa.UniqueConstraint("code", name=op.f("uq_location_shares_code")),
    )
    op.create_index(
        op.f("ix_location_shares_owner_user_id"),
        "location_shares",
        ["owner_user_id"],
        unique=False,
    )

def downgrade() -> None:
    op.drop_index(
        op.f("ix_location_shares_owner_user_id"),
        table_name="location_shares",
    )
    op.drop_table("location_shares")
