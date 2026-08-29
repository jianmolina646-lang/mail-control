"""Add platform administrator access.

Revision ID: 20260802_0008
Revises: 20260730_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_0008"
down_revision: str | None = "20260730_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute("""
        UPDATE users SET is_platform_admin = true
        WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'jheliz')
          AND role = 'OWNER'
    """)


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
