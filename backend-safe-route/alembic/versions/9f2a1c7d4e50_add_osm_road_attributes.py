"""Add OSM road attributes used by route scoring.

Revision ID: 9f2a1c7d4e50
Revises: f542cc6dfa76
"""

from alembic import op
import sqlalchemy as sa


revision = "9f2a1c7d4e50"
down_revision = "f542cc6dfa76"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable OSM attributes without changing existing records."""

    for name, column_type in (
        ("surface", sa.Text()),
        ("smoothness", sa.Text()),
        ("incline", sa.Float()),
        ("lit", sa.Boolean()),
        ("foot", sa.Text()),
        ("access", sa.Text()),
        ("crossing", sa.Text()),
        ("highway", sa.Text()),
    ):
        op.add_column("road_segments", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    """Remove the optional OSM attributes."""

    for name in (
        "highway",
        "crossing",
        "access",
        "foot",
        "lit",
        "incline",
        "smoothness",
        "surface",
    ):
        op.drop_column("road_segments", name)
