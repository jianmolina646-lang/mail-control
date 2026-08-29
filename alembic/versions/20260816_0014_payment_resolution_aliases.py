"""Recognize historical payment resolution aliases.

Revision ID: 20260816_0014
Revises: 20260816_0013
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260816_0014"
down_revision: str | None = "20260816_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("email_messages", "email_analyses", "alerts", "analysis_incidents"):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        WITH resolutions AS (
            SELECT DISTINCT ON (
                ea.tenant_id, em.mail_account_id,
                regexp_replace(lower(coalesce(ea.platform, ea.service, ea.category)),
                               '[^a-z0-9]+', '', 'g')
            )
                ea.tenant_id,
                em.mail_account_id,
                regexp_replace(lower(coalesce(ea.platform, ea.service, ea.category)),
                               '[^a-z0-9]+', '', 'g') AS service_key,
                ea.id AS analysis_id,
                em.id AS message_id,
                coalesce(em.received_at, em.created_at) AS event_at,
                ea.email_type
            FROM email_analyses ea
            JOIN email_messages em ON em.id = ea.email_message_id
            WHERE lower(replace(ea.email_type, '-', '_')) IN (
                    'payment_updated', 'payment_update_notice',
                    'payment_approved', 'payment_accepted', 'payment_successful'
                  )
               OR lower(coalesce(em.subject, '')) LIKE
                    '%dati di pagamento sono stati aggiornati%'
               OR lower(coalesce(em.subject, '')) LIKE
                    '%metodo di pagamento aggiornato%'
               OR lower(coalesce(em.snippet, '')) LIKE
                    '%aggiornato il tuo account con i nuovi dati di pagamento%'
            ORDER BY ea.tenant_id, em.mail_account_id, service_key,
                     coalesce(em.received_at, em.created_at) DESC,
                     ea.created_at DESC, ea.id DESC
        )
        UPDATE analysis_incidents incident
        SET status = 'resolved',
            current_analysis_id = resolution.analysis_id,
            current_message_id = resolution.message_id,
            opened_at = NULL,
            resolved_at = resolution.event_at,
            resolution_reason = resolution.email_type,
            last_event_received_at = resolution.event_at,
            updated_at = now()
        FROM resolutions resolution
        WHERE incident.tenant_id = resolution.tenant_id
          AND incident.mail_account_id = resolution.mail_account_id
          AND incident.service_key = resolution.service_key
          AND incident.incident_type IN (
              'payment_rejected', 'payment_method_expired', 'renewal_due'
          )
          AND resolution.event_at >= incident.last_event_received_at
        """
    )
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
          AND incident.status = 'resolved'
          AND incident.service_key = regexp_replace(
              lower(coalesce(ea.platform, ea.service, ea.category)), '[^a-z0-9]+', '', 'g'
          )
          AND coalesce(em.received_at, em.created_at) <= incident.last_event_received_at
        """
    )

    for table in ("email_messages", "email_analyses", "alerts", "analysis_incidents"):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    # This migration only reconciles derived state. Historical records remain intact.
    pass
