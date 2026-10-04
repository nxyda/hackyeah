"""make road segment OSM way IDs unique

Revision ID: c84f19a62d37
Revises: 7ac41d9f2b30
Create Date: 2026-10-03 22:25:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84f19a62d37"
down_revision: Union[str, Sequence[str], None] = "7ac41d9f2b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_road_segments_osm_way_id"),
        table_name="road_segments",
    )
    op.create_unique_constraint(
        op.f("uq_road_segments_osm_way_id"),
        "road_segments",
        ["osm_way_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_road_segments_osm_way_id"),
        "road_segments",
        type_="unique",
    )
    op.create_index(
        op.f("ix_road_segments_osm_way_id"),
        "road_segments",
        ["osm_way_id"],
        unique=False,
    )
