"""Add mail accounts, messages and synchronization runs.

Revision ID: 20260730_0003
Revises: 20260730_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260730_0003"
down_revision: str | None = "20260730_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

mail_provider = postgresql.ENUM(
    "GMAIL", "MICROSOFT", name="mail_provider", create_type=False
)
account_status = postgresql.ENUM(
    "CONNECTED",
    "SYNCING",
    "ERROR",
    "REAUTH_REQUIRED",
    "DISCONNECTED",
    name="account_status", create_type=False,
)
sync_kind = postgresql.ENUM(
    "INITIAL", "INCREMENTAL", name="sync_kind", create_type=False
)
sync_status = postgresql.ENUM(
    "RUNNING", "SUCCEEDED", "FAILED", name="sync_status", create_type=False
)


def upgrade() -> None:
    for enum in (mail_provider, account_status, sync_kind, sync_status):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "mail_accounts",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", mail_provider, nullable=False),
        sa.Column("provider_account_id", sa.String(length=320), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_scopes", sa.JSON(), nullable=False),
        sa.Column("status", account_status, nullable=False),
        sa.Column("history_cursor", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_mail_accounts_connected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_mail_accounts_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_accounts")),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_account_id",
            name=op.f("uq_mail_accounts_tenant_id"),
        ),
    )
    op.create_index(op.f("ix_mail_accounts_tenant_id"), "mail_accounts", ["tenant_id"])
    op.create_index(
        "ix_mail_accounts_tenant_status",
        "mail_accounts",
        ["tenant_id", "status"],
    )

    op.create_table(
        "email_messages",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("history_id", sa.String(length=64), nullable=True),
        sa.Column("internet_message_id", sa.String(length=998), nullable=True),
        sa.Column("sender", sa.String(length=998), nullable=True),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("internal_date_ms", sa.BigInteger(), nullable=True),
        sa.Column("size_estimate", sa.Integer(), nullable=True),
        sa.Column("label_ids", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_email_messages_mail_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_email_messages_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_messages")),
        sa.UniqueConstraint(
            "mail_account_id",
            "provider_message_id",
            name=op.f("uq_email_messages_mail_account_id"),
        ),
    )
    op.create_index(
        op.f("ix_email_messages_tenant_id"),
        "email_messages",
        ["tenant_id"],
    )
    op.create_index(
        "ix_email_messages_tenant_received",
        "email_messages",
        ["tenant_id", "received_at"],
    )
    op.create_index(
        "ix_email_messages_account_thread",
        "email_messages",
        ["mail_account_id", "thread_id"],
    )

    op.create_table(
        "sync_runs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sync_kind, nullable=False),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages_seen", sa.Integer(), nullable=False),
        sa.Column("messages_created", sa.Integer(), nullable=False),
        sa.Column("messages_updated", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mail_account_id"],
            ["mail_accounts.id"],
            name=op.f("fk_sync_runs_mail_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_sync_runs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index(
        "ix_sync_runs_tenant_started",
        "sync_runs",
        ["tenant_id", "started_at"],
    )
    op.create_index(
        "ix_sync_runs_account_status",
        "sync_runs",
        ["mail_account_id", "status"],
    )

    for table in ("mail_accounts", "email_messages", "sync_runs"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            """
        )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.drop_table("email_messages")
    op.drop_table("mail_accounts")
    for enum in (sync_status, sync_kind, account_status, mail_provider):
        enum.drop(op.get_bind(), checkfirst=True)
