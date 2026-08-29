"""Add chronological analysis incident state.

Revision ID: 20260815_0012
Revises: 20260815_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260815_0012"
down_revision: str | None = "20260815_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_incidents",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mail_account_id", sa.Uuid(), nullable=False),
        sa.Column("service_key", sa.String(160), nullable=False),
        sa.Column("incident_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("current_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("current_message_id", sa.Uuid(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_reason", sa.String(120)),
        sa.Column("last_event_received_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("status IN ('active', 'resolved')", name="valid_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["mail_account_id"], ["mail_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["current_analysis_id"], ["email_analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["current_message_id"], ["email_messages.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "mail_account_id",
            "service_key",
            "incident_type",
            name="uq_analysis_incidents_state_key",
        ),
    )
    op.create_index(
        "ix_analysis_incidents_tenant_status",
        "analysis_incidents",
        ["tenant_id", "status"],
    )
    op.execute("ALTER TABLE analysis_incidents ENABLE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON analysis_incidents
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )"""
    )

    # The runtime role owns these tables but FORCE RLS deliberately restricts
    # owners too. PostgreSQL DDL is transactional, so temporarily relaxing
    # FORCE here cannot become visible unless the migration also restores it.
    for table in ("email_messages", "email_analyses", "alerts"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    # Build the current projection from immutable history. Provider received_at,
    # not insertion time, is the primary ordering key.
    op.execute(
        """
        WITH failure_events AS (
            SELECT ea.tenant_id, em.mail_account_id,
                   regexp_replace(lower(coalesce(ea.platform, ea.service, ea.category)),
                                  '[^a-z0-9]+', '', 'g') AS service_key,
                   alert.value AS incident_type, ea.id AS analysis_id,
                   em.id AS message_id,
                   coalesce(em.received_at, em.created_at) AS event_at,
                   ea.created_at AS processed_at, 'active'::text AS status,
                   NULL::text AS resolution_reason
            FROM email_analyses ea
            JOIN email_messages em ON em.id = ea.email_message_id
            CROSS JOIN LATERAL json_array_elements_text(ea.alert_types) alert(value)
            WHERE alert.value IN (
                'payment_rejected', 'payment_method_expired', 'renewal_due'
            )
            UNION ALL
            SELECT ea.tenant_id, em.mail_account_id,
                   regexp_replace(lower(coalesce(ea.platform, ea.service, ea.category)),
                                  '[^a-z0-9]+', '', 'g'),
                   'account_suspended', ea.id, em.id,
                   coalesce(em.received_at, em.created_at), ea.created_at,
                   'active', NULL
            FROM email_analyses ea
            JOIN email_messages em ON em.id = ea.email_message_id
            WHERE lower(replace(ea.email_type, '-', '_')) IN (
                'account_suspended', 'account_disabled'
            )
        ), resolution_events AS (
            SELECT ea.tenant_id, em.mail_account_id,
                   regexp_replace(lower(coalesce(ea.platform, ea.service, ea.category)),
                                  '[^a-z0-9]+', '', 'g') AS service_key,
                   target.incident_type, ea.id, em.id,
                   coalesce(em.received_at, em.created_at), ea.created_at,
                   'resolved'::text, ea.email_type
            FROM email_analyses ea
            JOIN email_messages em ON em.id = ea.email_message_id
            CROSS JOIN LATERAL (
                SELECT unnest(CASE
                    WHEN lower(replace(ea.email_type, '-', '_')) IN (
                        'payment_updated', 'payment_approved', 'payment_accepted',
                        'payment_successful'
                    ) THEN ARRAY[
                        'payment_rejected', 'payment_method_expired', 'renewal_due'
                    ]
                    WHEN lower(replace(ea.email_type, '-', '_')) IN (
                        'renewed', 'renewal_completed', 'subscription_renewed'
                    ) THEN ARRAY['renewal_due']
                    WHEN lower(replace(ea.email_type, '-', '_')) IN (
                        'account_reactivated', 'account_active'
                    ) THEN ARRAY['account_suspended']
                    ELSE ARRAY[]::text[]
                END) AS incident_type
            ) target
        ), ranked AS (
            SELECT events.*,
                   row_number() OVER (
                       PARTITION BY tenant_id, mail_account_id, service_key, incident_type
                       ORDER BY event_at DESC, (status = 'resolved') DESC,
                                processed_at DESC, analysis_id DESC
                   ) AS position
            FROM (
                SELECT * FROM failure_events
                UNION ALL
                SELECT * FROM resolution_events
            ) events
        )
        INSERT INTO analysis_incidents (
            tenant_id, mail_account_id, service_key, incident_type, status,
            current_analysis_id, current_message_id, opened_at, resolved_at,
            resolution_reason, last_event_received_at, id
        )
        SELECT tenant_id, mail_account_id, service_key, incident_type, status,
               analysis_id, message_id,
               CASE WHEN status = 'active' THEN event_at END,
               CASE WHEN status = 'resolved' THEN event_at END,
               resolution_reason, event_at, gen_random_uuid()
        FROM ranked
        WHERE position = 1
        """
    )

    # Preserve alerts as history while closing every alert older than the
    # projected current state. For active incidents, only the newest alert stays open.
    op.execute(
        """
        UPDATE alerts alert
        SET resolved_at = incident.last_event_received_at,
            updated_at = now()
        FROM email_analyses ea, email_messages em, analysis_incidents incident
        WHERE alert.analysis_id = ea.id
          AND alert.email_message_id = em.id
          AND alert.resolved_at IS NULL
          AND incident.tenant_id = alert.tenant_id
          AND incident.mail_account_id = em.mail_account_id
          AND incident.incident_type = lower(alert.alert_type::text)
          AND incident.service_key = regexp_replace(
              lower(coalesce(ea.platform, ea.service, ea.category)), '[^a-z0-9]+', '', 'g'
          )
          AND coalesce(em.received_at, em.created_at) <= incident.last_event_received_at
          AND (
              incident.status = 'resolved'
              OR alert.analysis_id <> incident.current_analysis_id
          )
        """
    )

    for table in (
        "email_messages",
        "email_analyses",
        "alerts",
        "analysis_incidents",
    ):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("analysis_incidents")
