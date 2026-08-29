"""Add provider synchronization cursors.

Revision ID: 20260730_0004
Revises: 20260730_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0004"
down_revision: str | None = "20260730_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_sync_cursors",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("resource_key", sa.String(length=512), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=False),
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
            name=op.f("fk_mail_sync_cursors_mail_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_mail_sync_cursors_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_sync_cursors")),
        sa.UniqueConstraint(
            "mail_account_id",
            "resource_key",
            name=op.f("uq_mail_sync_cursors_mail_account_id"),
        ),
    )
    op.create_index(
        "ix_mail_sync_cursors_tenant_account",
        "mail_sync_cursors",
        ["tenant_id", "mail_account_id"],
    )
    op.execute("ALTER TABLE mail_sync_cursors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE mail_sync_cursors FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON mail_sync_cursors
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.drop_table("mail_sync_cursors")
