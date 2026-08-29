"""Add Microsoft Graph webhook subscription state.

Revision ID: 20260811_0010
Revises: 20260811_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0010"
down_revision: str | None = "20260811_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "microsoft_graph_subscriptions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.String(length=128), nullable=True),
        sa.Column("resource", sa.String(length=255), nullable=False, server_default="me/messages"),
        sa.Column("client_state", sa.String(length=128), nullable=False),
        sa.Column("expiration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notification_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_microsoft_graph_subscriptions_mail_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_microsoft_graph_subscriptions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_microsoft_graph_subscriptions")),
        sa.UniqueConstraint(
            "mail_account_id",
            name=op.f("uq_microsoft_graph_subscriptions_mail_account_id"),
        ),
        sa.UniqueConstraint(
            "subscription_id",
            name=op.f("uq_microsoft_graph_subscriptions_subscription_id"),
        ),
    )
    op.create_index(
        "ix_microsoft_graph_subscriptions_tenant_due",
        "microsoft_graph_subscriptions",
        ["tenant_id", "expiration_at"],
    )


def downgrade() -> None:
    op.drop_table("microsoft_graph_subscriptions")
