"""create base route and safety tables

Revision ID: b95dd0192b79
Revises: 65df00ceb079
Create Date: 2026-10-03 17:02:56.187490
"""
from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


revision: str = "b95dd0192b79"
down_revision: Union[str, Sequence[str], None] = "65df00ceb079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "crime_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category", sa.Enum("ASSAULT", "ROBBERY", "HARASSMENT", "THEFT", "VANDALISM", "OTHER", name="crime_event_category"), nullable=False),
        sa.Column("geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, dimension=2, from_text="ST_GeomFromEWKT", name="geometry"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("severity", sa.Double(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crime_events")),
    )
    op.create_table(
        "road_segments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=False),
        sa.Column("geom", geoalchemy2.types.Geometry(geometry_type="LINESTRING", srid=4326, dimension=2, from_text="ST_GeomFromEWKT", name="geometry"), nullable=False),
        sa.Column("length_m", sa.Double(), nullable=False),
        sa.Column("road_type", sa.Text(), nullable=False),
        sa.Column("lit_ratio", sa.Double(), nullable=True),
        sa.Column("is_tunnel", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_footway", sa.Boolean(), nullable=True),
        sa.Column("surveillance_nearby", sa.Boolean(), nullable=True),
        sa.Column("dist_to_safe_place_m", sa.Double(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length_m > 0", name=op.f("ck_road_segments_length_positive")),
        sa.CheckConstraint("lit_ratio IS NULL OR (lit_ratio >= 0 AND lit_ratio <= 1)", name=op.f("ck_road_segments_lit_ratio_range")),
        sa.CheckConstraint("dist_to_safe_place_m IS NULL OR dist_to_safe_place_m >= 0", name=op.f("ck_road_segments_safe_place_distance_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_road_segments")),
    )
    op.create_index(op.f("ix_road_segments_osm_way_id"), "road_segments", ["osm_way_id"], unique=False)
    op.create_table(
        "safe_places",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category", sa.Enum("POLICE", "HOSPITAL", "FIRE_STATION", "PHARMACY", "FUEL_STATION", "SHOP", "PUBLIC_TRANSPORT", "OTHER", name="safe_place_category"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, dimension=2, from_text="ST_GeomFromEWKT", name="geometry"), nullable=False),
        sa.Column("opening_hours_raw", sa.Text(), nullable=True),
        sa.Column("is_24_7", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_safe_places")),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category", sa.Enum("DANGER", "HARASSMENT", "POOR_LIGHTING", "BLOCKED_PATH", "SUSPICIOUS_ACTIVITY", "OTHER", name="report_category"), nullable=False),
        sa.Column("geom", geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, dimension=2, from_text="ST_GeomFromEWKT", name="geometry"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "RESOLVED", "EXPIRED", "REJECTED", name="report_status"), server_default="ACTIVE", nullable=False),
        sa.Column("confirmations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("confirmations >= 0", name=op.f("ck_reports_confirmations_non_negative")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_reports_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_user_id"), "reports", ["user_id"], unique=False)
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=False))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("users", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=255), type_=sa.Text(), existing_nullable=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.drop_column("users", "username")


def downgrade() -> None:
    """Downgrade schema."""

    op.add_column("users", sa.Column("username", sa.VARCHAR(length=50), autoincrement=False, nullable=False))
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.alter_column("users", "email", existing_type=sa.Text(), type_=sa.VARCHAR(length=255), existing_nullable=False)
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
    op.drop_index(op.f("ix_reports_user_id"), table_name="reports")
    op.drop_table("reports")
    op.drop_table("safe_places")
    op.drop_index(op.f("ix_road_segments_osm_way_id"), table_name="road_segments")
    op.drop_table("road_segments")
    op.drop_table("crime_events")
