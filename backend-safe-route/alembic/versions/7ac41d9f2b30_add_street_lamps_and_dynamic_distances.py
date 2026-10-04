"""add street lamps and calculate safe-place distances dynamically

Revision ID: 7ac41d9f2b30
Revises: 56e2f9a11c43
Create Date: 2026-10-03 22:10:00.000000
"""

from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


revision: str = "7ac41d9f2b30"
down_revision: Union[str, Sequence[str], None] = "56e2f9a11c43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_road_segments_lit_ratio_range"),
        "road_segments",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_road_segments_safe_place_distance_non_negative"),
        "road_segments",
        type_="check",
    )
    op.drop_column("road_segments", "lit_ratio")
    op.drop_column("road_segments", "surveillance_nearby")
    op.drop_column("road_segments", "dist_to_safe_place_m")
    op.create_table(
        "street_lamps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_street_lamps")),
    )

def downgrade() -> None:
    op.drop_table("street_lamps")
    op.add_column(
        "road_segments",
        sa.Column("lit_ratio", sa.Double(), nullable=True),
    )
    op.add_column(
        "road_segments",
        sa.Column("surveillance_nearby", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "road_segments",
        sa.Column("dist_to_safe_place_m", sa.Double(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_road_segments_lit_ratio_range"),
        "road_segments",
        "lit_ratio IS NULL OR (lit_ratio >= 0 AND lit_ratio <= 1)",
    )
    op.create_check_constraint(
        op.f("ck_road_segments_safe_place_distance_non_negative"),
        "road_segments",
        "dist_to_safe_place_m IS NULL OR dist_to_safe_place_m >= 0",
    )
