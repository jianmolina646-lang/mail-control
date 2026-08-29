"""Create the enterprise baseline.

Revision ID: 20260730_0001
Revises:
"""

from collections.abc import Sequence

revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Baseline intentionally has no domain tables."""


def downgrade() -> None:
    """Baseline intentionally has no domain tables."""
