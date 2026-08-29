"""Add dashboard and full-text search indexes.

Revision ID: 20260730_0006
Revises: 20260730_0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE email_messages
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector(
                'simple',
                coalesce(sender, '') || ' ' ||
                coalesce(subject, '') || ' ' ||
                coalesce(snippet, '')
            )
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_email_messages_search_vector "
        "ON email_messages USING gin (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_email_messages_tenant_cursor "
        "ON email_messages "
        "(tenant_id, (coalesce(received_at, created_at)) DESC, id DESC) "
        "WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_email_analyses_tenant_category_risk "
        "ON email_analyses (tenant_id, category, risk_level)"
    )
    op.execute(
        "CREATE INDEX ix_alerts_tenant_open_cursor "
        "ON alerts (tenant_id, created_at DESC, id DESC) "
        "WHERE resolved_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_alerts_tenant_open_cursor")
    op.execute("DROP INDEX IF EXISTS ix_email_analyses_tenant_category_risk")
    op.execute("DROP INDEX IF EXISTS ix_email_messages_tenant_cursor")
    op.execute("DROP INDEX IF EXISTS ix_email_messages_search_vector")
    op.execute("ALTER TABLE email_messages DROP COLUMN IF EXISTS search_vector")
