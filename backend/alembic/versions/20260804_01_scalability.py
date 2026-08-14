"""Baseline the existing schema and add scalability indexes.

Revision ID: 20260804_01
Revises: None
"""
from typing import Sequence, Union

from alembic import op

from app.core.db import Base
from app.models import models  # noqa: F401

revision: str = "20260804_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    Base.metadata.create_all(bind=connection)

    # Remove indexes duplicated by the former mix of explicit and implicit indexes.
    op.execute("DROP INDEX IF EXISTS ix_messages_received_at")
    op.execute("DROP INDEX IF EXISTS ix_message_received")
    op.execute("DROP INDEX IF EXISTS ix_agent_code_receipts_job_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_is_alert")

    # Pagination, history and foreign-key maintenance.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_message_received_id "
        "ON messages (received_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_message_account_received_id "
        "ON messages (account_id, received_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_alert_received_id "
        "ON messages (received_at DESC, id DESC) WHERE is_alert"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_events_created_at "
        "ON sync_events (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_subscriptions_latest_message_id "
        "ON subscriptions (latest_message_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_subscription_events_message_id "
        "ON subscription_events (message_id)"
    )

    # Trigram indexes support the existing contains searches (ILIKE '%text%').
    for column in ("subject", "from_addr", "from_name"):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_messages_{column}_trgm "
            f"ON messages USING gin ({column} gin_trgm_ops)"
        )


def downgrade() -> None:
    for name in (
        "ix_messages_from_name_trgm",
        "ix_messages_from_addr_trgm",
        "ix_messages_subject_trgm",
        "ix_subscription_events_message_id",
        "ix_subscriptions_latest_message_id",
        "ix_sync_events_created_at",
        "ix_messages_alert_received_id",
        "ix_message_account_received_id",
        "ix_message_received_id",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")
