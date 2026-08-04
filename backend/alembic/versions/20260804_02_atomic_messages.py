"""Make message ingestion idempotent across concurrent sync tasks.

Revision ID: 20260804_02
Revises: 20260804_01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260804_02"
down_revision: Union[str, None] = "20260804_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_messages_account_message_id_nonempty "
        "ON messages (account_id, message_id) WHERE message_id <> ''"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_messages_account_message_id_nonempty"
    )
