"""Persistencia del estado y el historial de suscripciones."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Alert, Message, Subscription, SubscriptionEvent
from .radar import Classification


def apply_classification(
    db: Session,
    *,
    account_id: int,
    message: Message,
    result: Classification,
) -> Subscription | None:
    """Actualiza la suscripción si el mensaje aporta un estado conocido."""
    if not result.service or result.status == "unknown":
        return None

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.account_id == account_id,
            Subscription.service == result.service,
        )
        .one_or_none()
    )
    previous_status = subscription.status if subscription else "unknown"
    now = message.received_at or datetime.now(timezone.utc)

    is_new = subscription is None
    if is_new:
        subscription = Subscription(
            account_id=account_id,
            service=result.service,
            detected_at=now,
        )
        db.add(subscription)
        db.flush()

    # Al reprocesar correos históricos, el más antiguo nunca debe sobrescribir
    # el estado aportado por un mensaje posterior.
    if not is_new and subscription.updated_at and now < subscription.updated_at:
        return subscription

    subscription.status = result.status
    subscription.severity = result.severity
    subscription.reason = result.reason
    subscription.score = result.score
    subscription.latest_message_id = message.id
    subscription.updated_at = now

    if previous_status != result.status:
        db.add(
            SubscriptionEvent(
                subscription_id=subscription.id,
                message_id=message.id,
                previous_status=previous_status,
                status=result.status,
                severity=result.severity,
                reason=result.reason,
                score=result.score,
                detected_at=now,
            )
        )

    if result.status == "active":
        (
            db.query(Alert)
            .filter(
                Alert.message_id.in_(
                    select(Message.id).where(Message.account_id == account_id)
                ),
                Alert.service == result.service,
                Alert.resolved.is_(False),
            )
            .update({Alert.resolved: True}, synchronize_session=False)
        )

    return subscription
