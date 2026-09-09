from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import aio_pika
import httpx
import structlog
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_object_session

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.microsoft import (
    MicrosoftError,
    MicrosoftGraphClient,
    MicrosoftReauthorizationRequired,
    MicrosoftTransientError,
)
from mail_control.modules.mail.models import (
    AccountStatus,
    MailAccount,
    MailProvider,
    MicrosoftGraphSubscription,
)
from mail_control.modules.mail.token_manager import provider_client
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings

logger = structlog.get_logger(__name__)
MICROSOFT_MESSAGES_RESOURCE = "me/messages"


def parse_graph_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def notification_identity(notification: dict[str, Any]) -> str:
    resource_data = notification.get("resourceData")
    if isinstance(resource_data, dict):
        resource_id = resource_data.get("id") or resource_data.get("@odata.id")
        if resource_id:
            return str(resource_id)
    for key in ("id", "resource", "lifecycleEvent"):
        value = notification.get(key)
        if value:
            return str(value)
    return json.dumps(notification, sort_keys=True)


async def enqueue_microsoft_sync(
    resources: Resources,
    *,
    tenant_id: Any,
    account_id: Any,
) -> None:
    channel = await resources.rabbitmq.channel()
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(
                    {
                        "tenant_id": str(tenant_id),
                        "mail_account_id": str(account_id),
                    }
                ).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="mail.sync.microsoft",
        )
    finally:
        await channel.close()


async def enqueue_from_graph_notification(
    session: Any,
    resources: Resources,
    settings: Settings,
    notification: dict[str, Any],
) -> bool:
    subscription_id = notification.get("subscriptionId")
    if not isinstance(subscription_id, str) or not subscription_id:
        raise ValueError("Microsoft Graph notification omitted subscriptionId")
    state = await session.scalar(
        select(MicrosoftGraphSubscription).where(
            MicrosoftGraphSubscription.subscription_id == subscription_id
        )
    )
    if state is None:
        logger.warning("microsoft_graph_subscription_not_found", subscription_id=subscription_id)
        return False
    if notification.get("clientState") != state.client_state:
        raise ValueError("unexpected Microsoft Graph clientState")

    state.last_notification_at = datetime.now(UTC)
    state.last_error = None
    lifecycle_event = notification.get("lifecycleEvent")
    if lifecycle_event:
        state.status = str(lifecycle_event)

    dedupe_id = notification_identity(notification)
    dedupe_key = f"mail-control:microsoft-graph:{subscription_id}:{dedupe_id}"
    try:
        claimed = await resources.redis.set(
            dedupe_key,
            "1",
            ex=settings.microsoft_graph_webhook_dedupe_seconds,
            nx=True,
        )
    except RedisError:
        logger.warning(
            "microsoft_graph_dedupe_unavailable",
            subscription_id=subscription_id,
        )
        claimed = True
    if not claimed:
        logger.info(
            "microsoft_graph_notification_duplicate",
            subscription_id=subscription_id,
        )
        await session.commit()
        return False

    await enqueue_microsoft_sync(
        resources,
        tenant_id=state.tenant_id,
        account_id=state.mail_account_id,
    )
    await session.commit()
    logger.info(
        "microsoft_graph_sync_enqueued",
        account_id=str(state.mail_account_id),
        subscription_id=subscription_id,
        lifecycle_event=lifecycle_event,
    )
    return True


async def graph_client_for_account(
    *,
    account: MailAccount,
    resources: Resources,
    settings: Settings,
    session: AsyncSession | None = None,
) -> MicrosoftGraphClient:
    session = session or async_object_session(account)
    if session is None:
        raise RuntimeError("Subscription renewal requires a persisted account session")
    client = await provider_client(account, session, resources, settings)
    if not isinstance(client, MicrosoftGraphClient):
        raise ValueError("Graph subscription requires a Microsoft connection")
    return client


async def ensure_graph_subscription(
    *,
    account: MailAccount,
    state: MicrosoftGraphSubscription | None,
    resources: Resources,
    settings: Settings,
) -> MicrosoftGraphSubscription:
    notification_url = settings.microsoft_graph_notification_url
    lifecycle_url = settings.microsoft_graph_lifecycle_url or notification_url
    if not notification_url or not lifecycle_url:
        raise MicrosoftError("Microsoft Graph webhook URL is not configured")
    if state is None:
        state = MicrosoftGraphSubscription(
            tenant_id=account.tenant_id,
            mail_account_id=account.id,
            resource=MICROSOFT_MESSAGES_RESOURCE,
            client_state=secrets.token_urlsafe(32)[:128],
        )
    client = await graph_client_for_account(account=account, resources=resources, settings=settings)
    requested_expiration = datetime.now(UTC) + timedelta(
        hours=settings.microsoft_graph_subscription_hours
    )
    try:
        if state.subscription_id:
            response = await client.renew_subscription(
                state.subscription_id,
                expiration_at=requested_expiration,
            )
        else:
            response = await client.create_subscription(
                notification_url=notification_url,
                lifecycle_url=lifecycle_url,
                resource=state.resource,
                expiration_at=requested_expiration,
                client_state=state.client_state,
            )
    except httpx.HTTPStatusError as error:
        if state.subscription_id and error.response.status_code in {404, 410}:
            state.subscription_id = None
            response = await client.create_subscription(
                notification_url=notification_url,
                lifecycle_url=lifecycle_url,
                resource=state.resource,
                expiration_at=requested_expiration,
                client_state=state.client_state,
            )
        else:
            raise
    state.subscription_id = str(response.get("id") or state.subscription_id)
    state.expiration_at = parse_graph_datetime(response.get("expirationDateTime"))
    state.renewed_at = datetime.now(UTC)
    state.status = "active"
    state.last_error = None
    return state


async def reauthorize_subscription(
    *,
    account: MailAccount,
    state: MicrosoftGraphSubscription,
    resources: Resources,
    settings: Settings,
) -> None:
    if not state.subscription_id:
        return
    client = await graph_client_for_account(account=account, resources=resources, settings=settings)
    await client.reauthorize_subscription(state.subscription_id)
    state.status = "active"
    state.last_error = None


async def renew_due_microsoft_graph_subscriptions(
    resources: Resources,
    settings: Settings,
) -> int:
    if not settings.microsoft_graph_webhook_enabled:
        return 0
    cutoff = datetime.now(UTC) + timedelta(
        hours=settings.microsoft_graph_subscription_renewal_hours
    )
    renewed = 0
    async with resources.system_database.session_factory() as session:
        accounts = (
            await session.execute(
                select(MailAccount, MicrosoftGraphSubscription)
                .outerjoin(
                    MicrosoftGraphSubscription,
                    MicrosoftGraphSubscription.mail_account_id == MailAccount.id,
                )
                .where(
                    MailAccount.provider == MailProvider.MICROSOFT,
                    MailAccount.status.in_((AccountStatus.CONNECTED, AccountStatus.ERROR)),
                    (
                        (MicrosoftGraphSubscription.id.is_(None))
                        | (MicrosoftGraphSubscription.expiration_at.is_(None))
                        | (MicrosoftGraphSubscription.expiration_at <= cutoff)
                        | (MicrosoftGraphSubscription.status != "active")
                    ),
                )
            )
        ).all()
        for account, state in accounts:
            try:
                if state is not None and state.status == "reauthorizationRequired":
                    await reauthorize_subscription(
                        account=account,
                        state=state,
                        resources=resources,
                        settings=settings,
                    )
                state = await ensure_graph_subscription(
                    account=account,
                    state=state,
                    resources=resources,
                    settings=settings,
                )
                session.add(state)
                renewed += 1
            except MicrosoftReauthorizationRequired as error:
                account.status = AccountStatus.REAUTH_REQUIRED
                account.last_error = str(error)
                if state is not None:
                    state.status = "reauth_required"
                    state.last_error = str(error)
                await TelegramAlerts(settings, resources.redis).account_issue(
                    account,
                    str(error),
                )
            except MicrosoftTransientError as error:
                if state is not None:
                    state.status = "transient_error"
                    state.last_error = str(error)
                logger.warning(
                    "microsoft_graph_subscription_transient_error",
                    account_id=str(account.id),
                    detail=str(error),
                )
            except Exception as error:
                if state is not None:
                    state.status = "error"
                    state.last_error = str(error)[:2000]
                logger.warning(
                    "microsoft_graph_subscription_renewal_failed",
                    account_id=str(account.id),
                    error_type=type(error).__name__,
                )
        await session.commit()
    return renewed
