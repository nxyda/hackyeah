"""add user profile fields and OAuth identities

Revision ID: 6aeb2daacbf5
Revises: b95dd0192b79
Create Date: 2026-10-03 20:15:11.648751
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6aeb2daacbf5"
down_revision: Union[str, Sequence[str], None] = "b95dd0192b79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Dodaje opcjonalny profil i tożsamości Google/Facebook."""

    op.add_column("users", sa.Column("given_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("family_name", sa.String(length=100), nullable=True))
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "google",
                "facebook",
                name="oauth_provider",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('google', 'facebook')",
            name=op.f("ck_user_identities_provider_supported"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identities")),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name=op.f("uq_user_identities_provider_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_user_identities_user_id"),
        "user_identities",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Usuwa zmianę tylko wtedy, gdy nie skasuje powiązań OAuth."""

    linked_identities = op.get_bind().execute(
        sa.text("SELECT count(*) FROM user_identities")
    ).scalar_one()
    if linked_identities:
        raise RuntimeError(
            "Cannot downgrade while OAuth identities exist; "
            "migrate or unlink those identities first."
        )

    op.drop_index(op.f("ix_user_identities_user_id"), table_name="user_identities")
    op.drop_table("user_identities")
    op.drop_column("users", "family_name")
    op.drop_column("users", "given_name")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.Text(),
        nullable=False,
    )
