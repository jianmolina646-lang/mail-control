"""Persist Gmail-like message state.

Revision ID: 20260827_0015
Revises: 20260816_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0015"
down_revision: str | None = "20260816_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_messages",
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "email_messages",
        sa.Column("is_starred", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "email_messages",
        sa.Column("mailbox", sa.String(length=16), server_default="inbox", nullable=False),
    )
    op.create_index("ix_email_messages_tenant_mailbox", "email_messages", ["tenant_id", "mailbox"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_tenant_mailbox", table_name="email_messages")
    op.drop_column("email_messages", "mailbox")
    op.drop_column("email_messages", "is_starred")
    op.drop_column("email_messages", "is_read")
