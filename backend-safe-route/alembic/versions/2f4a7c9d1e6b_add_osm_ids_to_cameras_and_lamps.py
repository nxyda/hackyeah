"""add OSM IDs to cameras and street lamps

Revision ID: 2f4a7c9d1e6b
Revises: c84f19a62d37
Create Date: 2026-10-03 22:48:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f4a7c9d1e6b"
down_revision: Union[str, Sequence[str], None] = "c84f19a62d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("osm_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_cameras_osm_id"),
        "cameras",
        ["osm_id"],
    )
    op.add_column(
        "street_lamps",
        sa.Column("osm_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_street_lamps_osm_id"),
        "street_lamps",
        ["osm_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_street_lamps_osm_id"),
        "street_lamps",
        type_="unique",
    )
    op.drop_column("street_lamps", "osm_id")
    op.drop_constraint(
        op.f("uq_cameras_osm_id"),
        "cameras",
        type_="unique",
    )
    op.drop_column("cameras", "osm_id")
