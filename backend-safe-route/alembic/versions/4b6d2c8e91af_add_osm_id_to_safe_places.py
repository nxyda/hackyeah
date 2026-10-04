"""add OSM ID to safe places

Revision ID: 4b6d2c8e91af
Revises: 3be8c1a72d94
Create Date: 2026-10-03 23:38:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b6d2c8e91af"
down_revision: Union[str, Sequence[str], None] = "3be8c1a72d94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "safe_places",
        sa.Column("osm_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_safe_places_osm_id"),
        "safe_places",
        ["osm_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_safe_places_osm_id"),
        "safe_places",
        type_="unique",
    )
    op.drop_column("safe_places", "osm_id")
