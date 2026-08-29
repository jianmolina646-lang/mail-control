"""Add SaaS plans and tenant subscriptions.

Revision ID: 20260730_0007
Revises: 20260730_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("max_accounts", sa.Integer(), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("max_messages_month", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tenant_subscriptions",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        "ix_tenant_subscriptions_status",
        "tenant_subscriptions",
        ["tenant_id", "status"],
    )
    op.execute("""
      INSERT INTO plans (id, code, name, max_accounts, max_users, max_messages_month, is_active)
      VALUES
        (gen_random_uuid(), 'starter', 'Starter', 10, 3, 10000, true),
        (gen_random_uuid(), 'growth', 'Growth', 100, 15, 250000, true),
        (gen_random_uuid(), 'enterprise', 'Enterprise', 1000, 100, 5000000, true)
    """)
    op.execute("""
      INSERT INTO tenant_subscriptions
        (id, tenant_id, plan_id, status, period_start, period_end)
      SELECT gen_random_uuid(), t.id, p.id, 'trialing', now(), now() + interval '30 days'
      FROM tenants t CROSS JOIN plans p WHERE p.code = 'starter'
    """)
    op.execute("ALTER TABLE tenant_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_subscriptions FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON tenant_subscriptions
      USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)""")


def downgrade() -> None:
    op.drop_table("tenant_subscriptions")
    op.drop_table("plans")
