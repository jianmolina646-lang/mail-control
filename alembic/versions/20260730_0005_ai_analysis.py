"""Add AI analysis, alerts and transactional outbox.

Revision ID: 20260730_0005
Revises: 20260730_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260730_0005"
down_revision: str | None = "20260730_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

risk_level = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level", create_type=False
)
alert_type = postgresql.ENUM(
    "PAYMENT_REJECTED",
    "PAYMENT_METHOD_EXPIRED",
    "RENEWAL_DUE",
    "PASSWORD_CHANGED",
    "EMAIL_CHANGED",
    "VERIFICATION_CODE",
    "ACCESS_ATTEMPT",
    "SECURITY",
    name="alert_type", create_type=False,
)
outbox_status = postgresql.ENUM(
    "PENDING", "PROCESSING", "PROCESSED", "FAILED",
    name="outbox_status", create_type=False,
)


def upgrade() -> None:
    for enum in (risk_level, alert_type, outbox_status):
        enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_analyses",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email_message_id", sa.Uuid(), nullable=False),
        sa.Column("service", sa.String(120)),
        sa.Column("platform", sa.String(120)),
        sa.Column("amount", sa.String(64)),
        sa.Column("currency", sa.String(12)),
        sa.Column("country", sa.String(80)),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False),
        sa.Column("email_type", sa.String(80), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("action_required", sa.Text()),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("alert_types", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("email_message_id"),
    )
    op.create_index(op.f("ix_email_analyses_tenant_id"), "email_analyses", ["tenant_id"])
    op.create_table(
        "alerts",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email_message_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("alert_type", alert_type, nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["email_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_tenant_created", "alerts", ["tenant_id", "created_at"])
    op.create_index("ix_alerts_tenant_resolved", "alerts", ["tenant_id", "resolved_at"])
    op.create_table(
        "outbox_events",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", outbox_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_outbox_events_status_available",
        "outbox_events",
        ["status", "available_at"],
    )
    for table in ("email_analyses", "alerts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true), ''
                )::uuid
            )"""
        )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("alerts")
    op.drop_table("email_analyses")
    for enum in (outbox_status, alert_type, risk_level):
        enum.drop(op.get_bind(), checkfirst=True)
