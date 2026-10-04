"""create cameras table

Revision ID: 8a6d2e1c4f90
Revises: 6aeb2daacbf5
Create Date: 2026-10-03 20:35:00.000000
"""

from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


revision: str = "8a6d2e1c4f90"
down_revision: Union[str, Sequence[str], None] = "6aeb2daacbf5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cameras",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cameras")),
    )


def downgrade() -> None:
    op.drop_table("cameras")
