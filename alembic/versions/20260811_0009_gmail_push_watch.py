"""Add Gmail push notification watch state.

Revision ID: 20260811_0009
Revises: 20260802_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0009"
down_revision: str | None = "20260802_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gmail_watch_states",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("history_id", sa.String(length=64), nullable=True),
        sa.Column("expiration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["mail_account_id"],
            ["mail_accounts.id"],
            name=op.f("fk_gmail_watch_states_mail_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_gmail_watch_states_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gmail_watch_states")),
        sa.UniqueConstraint("mail_account_id", name=op.f("uq_gmail_watch_states_mail_account_id")),
    )
    op.create_index(
        "ix_gmail_watch_states_tenant_due",
        "gmail_watch_states",
        ["tenant_id", "expiration_at"],
    )
    op.execute("ALTER TABLE gmail_watch_states ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gmail_watch_states FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON gmail_watch_states
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.drop_table("gmail_watch_states")
