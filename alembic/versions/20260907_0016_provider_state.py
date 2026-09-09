"""Separate provider state from explicit local organization.

Revision ID: 20260907_0016
Revises: 20260827_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_0016"
down_revision: str | None = "20260827_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("is_read", "is_starred"):
        op.add_column("email_messages", sa.Column(
            f"provider_{name}", sa.Boolean(), server_default=sa.false(), nullable=False
        ))
        op.add_column("email_messages", sa.Column(f"local_{name}", sa.Boolean()))
    op.add_column("email_messages", sa.Column(
        "provider_mailbox", sa.String(16), server_default="inbox", nullable=False
    ))
    op.add_column("email_messages", sa.Column("provider_folder_id", sa.String(512)))
    op.add_column("email_messages", sa.Column("local_mailbox", sa.String(16)))
    # Legacy defaults carry no user intent. Preserve observable local choices.
    op.execute("UPDATE email_messages SET local_is_read = true WHERE is_read = true")
    op.execute("UPDATE email_messages SET local_is_starred = true WHERE is_starred = true")
    op.execute("UPDATE email_messages SET local_mailbox = mailbox WHERE mailbox <> 'inbox'")


def downgrade() -> None:
    for name in ("local_mailbox", "provider_folder_id", "provider_mailbox",
                 "local_is_starred", "provider_is_starred", "local_is_read", "provider_is_read"):
        op.drop_column("email_messages", name)
