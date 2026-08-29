from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mail_control.modules.analysis.models import AlertType, EmailAnalysis, RiskLevel
from mail_control.modules.analysis.repository import AnalysisRepository
from mail_control.modules.analysis.schemas import AnalysisResult, Category
from mail_control.modules.analysis.service import (
    analysis_input,
    deduplicate_alert_types,
    incident_transition,
    suppress_confirmed_payment_alerts,
)
from mail_control.modules.mail.models import EmailMessage


def test_structured_analysis_accepts_expected_classification() -> None:
    result = AnalysisResult.model_validate(
        {
            "service": "Netflix",
            "platform": "Netflix",
            "amount": "39.90",
            "currency": "PEN",
            "country": "PE",
            "language": "es",
            "priority": "alta",
            "email_type": "payment_rejected",
            "category": "Pagos",
            "action_required": "Actualizar el método de pago",
            "risk_level": "high",
            "alert_types": ["payment_rejected"],
        }
    )
    assert result.category is Category.PAYMENTS
    assert result.risk_level is RiskLevel.HIGH
    assert result.alert_types == [AlertType.PAYMENT_REJECTED]


def test_structured_analysis_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                "language": "es",
                "priority": "baja",
                "email_type": "other",
                "category": "inventada",
                "risk_level": "low",
            }
        )


def test_analysis_input_excludes_credentials_and_raw_payload() -> None:
    message = EmailMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        mail_account_id=uuid4(),
        provider_message_id="provider-id",
        sender="billing@example.com",
        recipients=["owner@example.com"],
        subject="Payment",
        snippet="Payment received",
        label_ids=[],
        payload={"raw": "large-sensitive-provider-payload"},
    )
    data = analysis_input(message)
    assert data["subject"] == "Payment"
    assert data["body"] == "Payment received"
    assert "payload" not in data


def test_analysis_input_uses_full_microsoft_body() -> None:
    message = EmailMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        mail_account_id=uuid4(),
        provider_message_id="provider-id",
        sender="billing@example.com",
        recipients=["owner@example.com"],
        subject="Payment update",
        snippet="Your payment method...",
        label_ids=[],
        payload={
            "body": {
                "contentType": "html",
                "content": "<p>Your payment method was updated successfully.</p>",
            }
        },
    )

    data = analysis_input(message)

    assert data["body"] == "Your payment method was updated successfully."


def test_confirmed_payment_update_suppresses_false_alert() -> None:
    result = AnalysisResult.model_validate(
        {
            "service": "Netflix",
            "platform": "Netflix",
            "language": "es",
            "priority": "alta",
            "email_type": "payment_rejected",
            "category": "Pagos",
            "action_required": "Actualizar el método de pago",
            "risk_level": "high",
            "alert_types": ["payment_rejected"],
        }
    )

    changed = suppress_confirmed_payment_alerts(
        result,
        {
            "subject": "Actualización de la forma de pago",
            "body": (
                "Como solicitaste, actualizamos tu información con la nueva "
                "forma de pago. La membresía se renovará automáticamente."
            ),
        },
    )

    assert changed is True
    assert result.alert_types == []
    assert result.action_required is None
    assert result.risk_level is RiskLevel.LOW


def test_duplicate_alert_types_are_removed_without_changing_order() -> None:
    result = analysis_result(
        email_type="payment_rejected",
        alert_types=["payment_rejected", "renewal_due", "payment_rejected"],
    )

    deduplicate_alert_types(result)

    assert result.alert_types == [AlertType.PAYMENT_REJECTED, AlertType.RENEWAL_DUE]


def analysis_result(*, email_type: str, alert_types: list[str]) -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "service": "Netflix",
            "platform": "Netflix",
            "language": "es",
            "priority": "alta" if alert_types else "baja",
            "email_type": email_type,
            "category": "Netflix",
            "action_required": "Revisar" if alert_types else None,
            "risk_level": "high" if alert_types else "low",
            "alert_types": alert_types,
        }
    )


def test_payment_rejected_then_payment_approved_resolves_current_incident() -> None:
    opened, resolved, key = incident_transition(
        analysis_result(email_type="payment_rejected", alert_types=["payment_rejected"]),
        {"subject": "No pudimos procesar tu pago"},
    )
    assert (opened, resolved, key) == ({"payment_rejected"}, set(), "netflix")

    opened, resolved, key = incident_transition(
        analysis_result(email_type="payment_approved", alert_types=[]),
        {"subject": "Pago aprobado"},
    )
    assert opened == set()
    assert resolved == {"payment_rejected", "payment_method_expired", "renewal_due"}
    assert key == "netflix"


def test_italian_payment_update_notice_resolves_payment_incidents() -> None:
    opened, resolved, key = incident_transition(
        analysis_result(email_type="payment_update_notice", alert_types=[]),
        {
            "subject": "I tuoi dati di pagamento sono stati aggiornati",
            "snippet": (
                "Abbiamo aggiornato il tuo account con i nuovi dati di pagamento."
            ),
        },
    )

    assert opened == set()
    assert resolved == {"payment_rejected", "payment_method_expired", "renewal_due"}
    assert key == "netflix"


def test_italian_payment_confirmation_text_resolves_unknown_analysis_alias() -> None:
    opened, resolved, _ = incident_transition(
        analysis_result(email_type="payment_notice", alert_types=[]),
        {"subject": "Metodo di pagamento aggiornato"},
    )

    assert opened == set()
    assert resolved == {"payment_rejected", "payment_method_expired", "renewal_due"}


def test_account_suspended_then_reactivated_resolves_current_incident() -> None:
    opened, resolved, _ = incident_transition(
        analysis_result(email_type="account_suspended", alert_types=[]),
        {"subject": "Cuenta suspendida"},
    )
    assert opened == {"account_suspended"}
    assert resolved == set()

    opened, resolved, _ = incident_transition(
        analysis_result(email_type="account_reactivated", alert_types=[]),
        {"subject": "Tu cuenta fue reactivada"},
    )
    assert opened == set()
    assert resolved == {"account_suspended"}


def test_renewal_pending_then_renewed_resolves_current_incident() -> None:
    opened, resolved, _ = incident_transition(
        analysis_result(email_type="renewal_due", alert_types=["renewal_due"]),
        {"subject": "Renovación pendiente"},
    )
    assert opened == {"renewal_due"}
    assert resolved == set()

    opened, resolved, _ = incident_transition(
        analysis_result(email_type="subscription_renewed", alert_types=[]),
        {"subject": "Suscripción renovada"},
    )
    assert opened == set()
    assert resolved == {"renewal_due"}


class CapturingScalarSession:
    def __init__(self) -> None:
        self.statement: object | None = None

    async def scalar(self, statement: object) -> None:
        self.statement = statement


class FlushSession:
    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fail_rolls_back_broken_transaction_before_updating_event() -> None:
    session = MagicMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    repository = AnalysisRepository(session)
    event = SimpleNamespace(id=uuid4(), attempts=3)

    await repository.fail(event, RuntimeError("duplicate alert"))  # type: ignore[arg-type]

    session.rollback.assert_awaited_once()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_incident_upsert_rejects_older_backfill() -> None:
    from datetime import UTC, datetime

    from sqlalchemy.dialects import postgresql

    session = CapturingScalarSession()
    repository = AnalysisRepository(session)  # type: ignore[arg-type]
    message = EmailMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        mail_account_id=uuid4(),
        provider_message_id="backfill-old",
        recipients=[],
        label_ids=[],
        payload={},
    )
    analysis = EmailAnalysis(
        id=uuid4(),
        tenant_id=message.tenant_id,
        email_message_id=message.id,
        language="es",
        priority="alta",
        email_type="payment_rejected",
        category="Pagos",
        risk_level=RiskLevel.HIGH,
        alert_types=["payment_rejected"],
        model="test",
        prompt_version="test",
    )

    await repository._upsert_incident(
        message=message,
        analysis=analysis,
        service_key="netflix",
        incident_type="payment_rejected",
        status="active",
        event_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert session.statement is not None
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "excluded.last_event_received_at > analysis_incidents.last_event_received_at" in sql
    assert "excluded.status =" in sql


@pytest.mark.asyncio
async def test_rejected_backfill_alert_is_immediately_resolved() -> None:
    from datetime import UTC, datetime

    repository = AnalysisRepository(FlushSession())  # type: ignore[arg-type]
    repository._upsert_incident = AsyncMock(return_value=False)  # type: ignore[method-assign]
    repository._resolve_rejected_backfill_alert = AsyncMock()  # type: ignore[method-assign]
    message = EmailMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        mail_account_id=uuid4(),
        provider_message_id="old-provider-message",
        recipients=[],
        label_ids=[],
        payload={},
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    analysis = EmailAnalysis(
        id=uuid4(),
        tenant_id=message.tenant_id,
        email_message_id=message.id,
        language="es",
        priority="alta",
        email_type="payment_rejected",
        category="Pagos",
        risk_level=RiskLevel.HIGH,
        alert_types=["payment_rejected"],
        model="test",
        prompt_version="test",
    )

    await repository.reconcile_incidents(
        message=message,
        analysis=analysis,
        service_key="netflix",
        opened={"payment_rejected"},
        resolved=set(),
    )

    repository._resolve_rejected_backfill_alert.assert_awaited_once()
