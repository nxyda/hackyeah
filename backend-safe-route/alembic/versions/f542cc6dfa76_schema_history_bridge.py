"""Restore the missing migration node used by the deployed database."""

from typing import Sequence, Union

from alembic import op


revision: str = "f542cc6dfa76"
down_revision: Union[str, Sequence[str], None] = (
    "2f4a7c9d1e6b",
    "4b6d2c8e91af",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep the already-applied schema history compatible with this checkout."""


def downgrade() -> None:
    """There is no schema operation to reverse for this history bridge."""
