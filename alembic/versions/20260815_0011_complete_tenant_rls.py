"""Complete tenant row-level security coverage.

Revision ID: 20260815_0011
Revises: 20260811_0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260815_0011"
down_revision: str | None = "20260811_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("outbox_events", "microsoft_graph_subscriptions")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'''CREATE POLICY tenant_isolation ON "{table}"
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )'''
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
