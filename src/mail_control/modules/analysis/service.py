from __future__ import annotations

import re
import unicodedata

from mail_control.modules.analysis.client import PROMPT_VERSION, AnalysisClient
from mail_control.modules.analysis.models import (
    Alert,
    EmailAnalysis,
    OutboxEvent,
    RiskLevel,
)
from mail_control.modules.analysis.repository import AnalysisRepository
from mail_control.modules.analysis.schemas import AnalysisResult
from mail_control.modules.mail.content import message_body
from mail_control.modules.mail.models import EmailMessage, MailProvider

PAYMENT_ALERT_VALUES = {
    "payment_rejected",
    "payment_method_expired",
    "renewal_due",
}
CONFIRMED_PAYMENT_MARKERS = (
    "actualizamos tu información con la nueva forma de pago",
    "método de pago fue actualizado",
    "forma de pago fue actualizada",
    "pago recibido",
    "pago realizado",
    "pago exitoso",
    "payment method has been updated",
    "payment was successful",
    "i tuoi dati di pagamento sono stati aggiornati",
    "metodo di pagamento aggiornato",
    "metodo di pagamento è stato aggiornato",
    "abbiamo aggiornato il tuo account con i nuovi dati di pagamento",
)
PAYMENT_FAILURE_MARKERS = (
    "pago rechazado",
    "pago fallido",
    "no pudimos procesar",
    "problema con tu pago",
    "método de pago vencido",
    "actualiza tu forma de pago",
    "actualizar tu forma de pago",
    "payment declined",
    "payment failed",
    "update your payment",
)
RENEWAL_CONFIRMED_MARKERS = (
    "renovación completada",
    "renovación confirmada",
    "suscripción renovada",
    "membresía renovada",
    "renewal completed",
    "subscription renewed",
)
ACCOUNT_REACTIVATED_MARKERS = (
    "cuenta reactivada",
    "cuenta vuelve a estar activa",
    "cuenta está activa nuevamente",
    "account reactivated",
    "account is active again",
)


def normalized_service_key(result: AnalysisResult) -> str:
    value = result.platform or result.service or result.category.value
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold()) or "unknown"


def incident_transition(
    result: AnalysisResult,
    email_data: dict[str, object],
) -> tuple[set[str], set[str], str]:
    """Return incident types opened/resolved by this single chronological event."""

    text = " ".join(
        str(email_data.get(field) or "") for field in ("subject", "snippet", "body")
    ).casefold()
    email_type = result.email_type.casefold().replace("-", "_").replace(" ", "_")
    opened = {item.value for item in result.alert_types if item.value in PAYMENT_ALERT_VALUES}
    if any(token in email_type for token in ("account_suspended", "account_disabled")):
        opened.add("account_suspended")

    resolved: set[str] = set()
    payment_confirmed = email_type in {
        "payment_updated",
        "payment_update_notice",
        "payment_approved",
        "payment_accepted",
        "payment_successful",
    } or any(marker in text for marker in CONFIRMED_PAYMENT_MARKERS)
    if payment_confirmed and not any(marker in text for marker in PAYMENT_FAILURE_MARKERS):
        resolved.update({"payment_rejected", "payment_method_expired", "renewal_due"})
    if email_type in {"renewed", "renewal_completed", "subscription_renewed"} or any(
        marker in text for marker in RENEWAL_CONFIRMED_MARKERS
    ):
        resolved.add("renewal_due")
    if email_type in {"account_reactivated", "account_active"} or any(
        marker in text for marker in ACCOUNT_REACTIVATED_MARKERS
    ):
        resolved.add("account_suspended")
    return opened, resolved, normalized_service_key(result)


def analysis_input(message: EmailMessage) -> dict[str, object]:
    provider = (
        MailProvider.GMAIL if "payload" in message.payload else MailProvider.MICROSOFT
    )
    body = message_body(message.payload, provider, message.snippet)
    return {
        "sender": message.sender,
        "recipients": message.recipients,
        "subject": message.subject,
        "snippet": message.snippet,
        "body": body[:12000] if body else None,
        "received_at": message.received_at,
    }


def suppress_confirmed_payment_alerts(
    result: AnalysisResult,
    email_data: dict[str, object],
) -> bool:
    text = " ".join(
        str(email_data.get(field) or "") for field in ("subject", "snippet", "body")
    ).casefold()
    confirmed = any(marker in text for marker in CONFIRMED_PAYMENT_MARKERS)
    failed = any(marker in text for marker in PAYMENT_FAILURE_MARKERS)
    if not confirmed or failed:
        return False
    remaining = [
        alert for alert in result.alert_types if alert.value not in PAYMENT_ALERT_VALUES
    ]
    if len(remaining) == len(result.alert_types):
        return False
    result.alert_types = remaining
    result.action_required = None
    result.email_type = "payment_updated"
    if not remaining:
        result.priority = "baja"
        result.risk_level = RiskLevel.LOW
    return True


def deduplicate_alert_types(result: AnalysisResult) -> None:
    """Keep the model order while preventing duplicate active alerts."""

    result.alert_types = list(dict.fromkeys(result.alert_types))


class AnalysisService:
    def __init__(
        self,
        repository: AnalysisRepository,
        client: AnalysisClient,
    ) -> None:
        self.repository = repository
        self.client = client

    async def process(self, event: OutboxEvent, message: EmailMessage) -> None:
        if await self.repository.existing_analysis(message.id):
            await self.repository.complete(event)
            return
        email_data = analysis_input(message)
        result = await self.client.analyze(email_data)
        suppress_confirmed_payment_alerts(result, email_data)
        deduplicate_alert_types(result)
        analysis = EmailAnalysis(
            tenant_id=message.tenant_id,
            email_message_id=message.id,
            service=result.service,
            platform=result.platform,
            amount=result.amount,
            currency=result.currency,
            country=result.country,
            language=result.language,
            priority=result.priority,
            email_type=result.email_type,
            category=result.category.value,
            action_required=result.action_required,
            risk_level=result.risk_level,
            alert_types=[item.value for item in result.alert_types],
            model=self.client.model,
            prompt_version=PROMPT_VERSION,
        )
        self.repository.add(analysis)
        await self.repository.session.flush()
        for alert_type in result.alert_types:
            self.repository.add(
                Alert(
                    tenant_id=message.tenant_id,
                    email_message_id=message.id,
                    analysis_id=analysis.id,
                    alert_type=alert_type,
                    title=f"{result.category.value}: {alert_type.value}",
                    detail=result.action_required,
                    risk_level=result.risk_level,
                )
            )
        opened, resolved, service_key = incident_transition(result, email_data)
        await self.repository.reconcile_incidents(
            message=message,
            analysis=analysis,
            service_key=service_key,
            opened=opened,
            resolved=resolved,
        )
        await self.repository.complete(event)
