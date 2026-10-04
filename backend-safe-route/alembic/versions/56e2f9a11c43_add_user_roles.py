"""add user roles

Revision ID: 56e2f9a11c43
Revises: 3d67a4b18c20
Create Date: 2026-10-03 21:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "56e2f9a11c43"
down_revision: Union[str, Sequence[str], None] = "3d67a4b18c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=5),
            server_default="user",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_users_user_role"),
        "users",
        "role IN ('user', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_user_role"), "users", type_="check")
    op.drop_column("users", "role")
