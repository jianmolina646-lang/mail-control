from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.modules.analysis.models import (
    Alert,
    AlertType,
    AnalysisIncident,
    EmailAnalysis,
    OutboxEvent,
    OutboxStatus,
)
from mail_control.modules.mail.models import EmailMessage


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(self) -> OutboxEvent | None:
        event = await self.session.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                OutboxEvent.available_at <= datetime.now(UTC),
                OutboxEvent.attempts < 8,
            )
            .order_by(OutboxEvent.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if event:
            event.status = OutboxStatus.PROCESSING
            event.attempts += 1
            await self.session.commit()
        return event

    async def message(self, tenant_id: UUID, message_id: UUID) -> EmailMessage | None:
        return cast(
            EmailMessage | None,
            await self.session.scalar(
                select(EmailMessage).where(
                    EmailMessage.tenant_id == tenant_id,
                    EmailMessage.id == message_id,
                )
            ),
        )

    async def existing_analysis(self, message_id: UUID) -> EmailAnalysis | None:
        return cast(
            EmailAnalysis | None,
            await self.session.scalar(
                select(EmailAnalysis).where(
                    EmailAnalysis.email_message_id == message_id
                )
            ),
        )

    def add(self, entity: EmailAnalysis | Alert) -> None:
        self.session.add(entity)

    async def reconcile_incidents(
        self,
        *,
        message: EmailMessage,
        analysis: EmailAnalysis,
        service_key: str,
        opened: set[str],
        resolved: set[str],
    ) -> None:
        """Advance current state only when this is the newest provider event."""

        if not opened and not resolved:
            return
        await self.session.flush()
        event_at = message.received_at or message.created_at
        for incident_type in opened:
            changed = await self._upsert_incident(
                message=message,
                analysis=analysis,
                service_key=service_key,
                incident_type=incident_type,
                status="active",
                event_at=event_at,
            )
            if changed:
                await self._resolve_matching_alerts(
                    message=message,
                    analysis=analysis,
                    service_key=service_key,
                    incident_type=incident_type,
                    event_at=event_at,
                    exclude_current=True,
                )
            else:
                await self._resolve_rejected_backfill_alert(
                    message=message,
                    analysis=analysis,
                    service_key=service_key,
                    incident_type=incident_type,
                )
        for incident_type in resolved:
            changed = await self._upsert_incident(
                message=message,
                analysis=analysis,
                service_key=service_key,
                incident_type=incident_type,
                status="resolved",
                event_at=event_at,
            )
            if changed:
                await self._resolve_matching_alerts(
                    message=message,
                    analysis=analysis,
                    service_key=service_key,
                    incident_type=incident_type,
                    event_at=event_at,
                    exclude_current=False,
                )

    async def _upsert_incident(
        self,
        *,
        message: EmailMessage,
        analysis: EmailAnalysis,
        service_key: str,
        incident_type: str,
        status: str,
        event_at: datetime,
    ) -> bool:
        values = {
            "tenant_id": message.tenant_id,
            "mail_account_id": message.mail_account_id,
            "service_key": service_key,
            "incident_type": incident_type,
            "status": status,
            "current_analysis_id": analysis.id,
            "current_message_id": message.id,
            "opened_at": event_at if status == "active" else None,
            "resolved_at": event_at if status == "resolved" else None,
            "resolution_reason": analysis.email_type if status == "resolved" else None,
            "last_event_received_at": event_at,
        }
        base_statement = insert(AnalysisIncident).values(**values)
        excluded = base_statement.excluded
        statement = base_statement.on_conflict_do_update(
            constraint="uq_analysis_incidents_state_key",
            set_={
                "status": excluded.status,
                "current_analysis_id": excluded.current_analysis_id,
                "current_message_id": excluded.current_message_id,
                "opened_at": excluded.opened_at,
                "resolved_at": excluded.resolved_at,
                "resolution_reason": excluded.resolution_reason,
                "last_event_received_at": excluded.last_event_received_at,
                "updated_at": func.now(),
            },
            where=or_(
                excluded.last_event_received_at > AnalysisIncident.last_event_received_at,
                and_(
                    excluded.last_event_received_at == AnalysisIncident.last_event_received_at,
                    excluded.status == "resolved",
                ),
            ),
        ).returning(AnalysisIncident.id)
        return await self.session.scalar(statement) is not None

    async def _resolve_rejected_backfill_alert(
        self,
        *,
        message: EmailMessage,
        analysis: EmailAnalysis,
        service_key: str,
        incident_type: str,
    ) -> None:
        try:
            alert_type = AlertType(incident_type)
        except ValueError:
            return
        state_time = await self.session.scalar(
            select(AnalysisIncident.last_event_received_at).where(
                AnalysisIncident.tenant_id == message.tenant_id,
                AnalysisIncident.mail_account_id == message.mail_account_id,
                AnalysisIncident.service_key == service_key,
                AnalysisIncident.incident_type == incident_type,
            )
        )
        if state_time is None:
            return
        await self.session.execute(
            update(Alert)
            .where(
                Alert.tenant_id == message.tenant_id,
                Alert.analysis_id == analysis.id,
                Alert.alert_type == alert_type,
                Alert.resolved_at.is_(None),
            )
            .values(resolved_at=state_time)
        )

    async def _resolve_matching_alerts(
        self,
        *,
        message: EmailMessage,
        analysis: EmailAnalysis,
        service_key: str,
        incident_type: str,
        event_at: datetime,
        exclude_current: bool,
    ) -> None:
        try:
            alert_type = AlertType(incident_type)
        except ValueError:
            return
        sql_service_key = func.regexp_replace(
            func.lower(
                func.coalesce(
                    EmailAnalysis.platform,
                    EmailAnalysis.service,
                    EmailAnalysis.category,
                )
            ),
            "[^a-z0-9]+",
            "",
            "g",
        )
        matching = (
            select(Alert.id)
            .join(EmailAnalysis, EmailAnalysis.id == Alert.analysis_id)
            .join(EmailMessage, EmailMessage.id == Alert.email_message_id)
            .where(
                Alert.tenant_id == message.tenant_id,
                Alert.alert_type == alert_type,
                Alert.resolved_at.is_(None),
                EmailMessage.mail_account_id == message.mail_account_id,
                func.coalesce(EmailMessage.received_at, EmailMessage.created_at) <= event_at,
                sql_service_key == service_key,
            )
        )
        if exclude_current:
            matching = matching.where(Alert.analysis_id != analysis.id)
        await self.session.execute(
            update(Alert).where(Alert.id.in_(matching)).values(resolved_at=event_at)
        )

    async def complete(self, event: OutboxEvent) -> None:
        event.status = OutboxStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        event.last_error = None
        await self.session.commit()

    async def fail(self, event: OutboxEvent, error: Exception) -> None:
        event_id = event.id
        attempts = event.attempts
        await self.session.rollback()
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                status=OutboxStatus.FAILED,
                last_error=str(error)[:2000],
                available_at=datetime.now(UTC)
                + timedelta(seconds=min(3600, 2**attempts * 15)),
            )
        )
        await self.session.commit()
