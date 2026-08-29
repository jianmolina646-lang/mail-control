from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import aio_pika
import httpx
import structlog
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.gmail import GmailClient, GmailError, GmailReauthRequired
from mail_control.modules.mail.models import (
    AccountStatus,
    GmailWatchState,
    MailAccount,
    MailProvider,
)
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings
from mail_control.worker import access_token, mark_reauth_required

logger = structlog.get_logger(__name__)


def decode_pubsub_payload(envelope: dict[str, Any]) -> dict[str, str]:
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise ValueError("Pub/Sub envelope omitted message")
    encoded = message.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Pub/Sub message omitted data")
    padded = encoded + "=" * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    email = payload.get("emailAddress")
    history_id = payload.get("historyId")
    if not isinstance(email, str) or not isinstance(history_id, int | str):
        raise ValueError("Gmail push payload omitted emailAddress or historyId")
    return {"emailAddress": email.casefold(), "historyId": str(history_id)}


async def verify_pubsub_push_request(
    *,
    authorization: str | None,
    verification_token: str | None,
    provided_token: str | None,
    expected_service_account: str | None,
    expected_audience: str | None,
    redis: Any,
) -> None:
    if verification_token and provided_token != verification_token:
        raise ValueError("invalid Pub/Sub verification token")
    if not expected_service_account:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("missing Pub/Sub bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    cache_key = f"mail-control:pubsub-oidc:{token[-32:]}"
    cached = await redis.get(cache_key)
    if cached == "1":
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": token},
        )
    response.raise_for_status()
    claims = response.json()
    if claims.get("email") != expected_service_account:
        raise ValueError("unexpected Pub/Sub service account")
    if claims.get("email_verified") not in {True, "true", "True"}:
        raise ValueError("Pub/Sub service account email is not verified")
    if expected_audience and claims.get("aud") != expected_audience:
        raise ValueError("unexpected Pub/Sub token audience")
    expires_at = int(claims.get("exp", "0") or "0")
    ttl = max(min(expires_at - int(datetime.now(UTC).timestamp()), 300), 10)
    await redis.set(cache_key, "1", ex=ttl)


async def enqueue_gmail_sync(
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
            routing_key="mail.sync.gmail",
        )
    finally:
        await channel.close()


async def enqueue_from_push(
    session: AsyncSession,
    resources: Resources,
    settings: Settings,
    *,
    email: str,
    history_id: str,
) -> bool:
    account = await session.scalar(
        select(MailAccount).where(
            MailAccount.provider == MailProvider.GMAIL,
            MailAccount.provider_account_id == email.casefold(),
            MailAccount.status.in_((AccountStatus.CONNECTED, AccountStatus.ERROR)),
        )
    )
    if account is None:
        logger.warning("gmail_push_account_not_found", email=email)
        return False
    dedupe_key = f"mail-control:gmail-push:{account.id}:{history_id}"
    try:
        claimed = await resources.redis.set(
            dedupe_key,
            "1",
            ex=settings.gmail_push_dedupe_seconds,
            nx=True,
        )
    except RedisError:
        logger.warning("gmail_push_dedupe_unavailable", account_id=str(account.id))
        claimed = True
    if not claimed:
        logger.info("gmail_push_duplicate", account_id=str(account.id), history_id=history_id)
        return False
    await enqueue_gmail_sync(resources, tenant_id=account.tenant_id, account_id=account.id)
    logger.info("gmail_push_sync_enqueued", account_id=str(account.id), history_id=history_id)
    return True


def watch_expiration(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except (TypeError, ValueError, OverflowError):
        return None


async def renew_gmail_watch(
    *,
    account: MailAccount,
    state: GmailWatchState | None,
    resources: Resources,
    settings: Settings,
) -> GmailWatchState:
    if not settings.gmail_pubsub_topic:
        raise GmailError("Gmail Pub/Sub topic is not configured")
    cipher = CredentialCipher(settings.credential_encryption_key or settings.app_secret_key)
    token, expires_at, rotated_refresh_token = await access_token(
        settings,
        resources,
        account.encrypted_access_token,
        account.access_token_expires_at,
        account.encrypted_refresh_token,
    )
    account.encrypted_access_token = cipher.encrypt(token)
    account.access_token_expires_at = expires_at
    if rotated_refresh_token:
        account.encrypted_refresh_token = cipher.encrypt(rotated_refresh_token)
    response = await GmailClient(token).watch(
        topic_name=settings.gmail_pubsub_topic,
        label_ids=settings.gmail_watch_label_ids,
    )
    now = datetime.now(UTC)
    if state is None:
        state = GmailWatchState(
            tenant_id=account.tenant_id,
            mail_account_id=account.id,
            status="active",
        )
    state.history_id = str(response.get("historyId")) if response.get("historyId") else None
    state.expiration_at = watch_expiration(response.get("expiration"))
    state.renewed_at = now
    state.status = "active"
    state.last_error = None
    logger.info(
        "gmail_watch_registered",
        account_id=str(account.id),
        expiration_at=state.expiration_at.isoformat() if state.expiration_at else None,
    )
    return state


async def renew_due_gmail_watches(resources: Resources, settings: Settings) -> int:
    if not settings.gmail_push_enabled:
        return 0
    if not settings.gmail_pubsub_topic:
        logger.warning("gmail_watch_disabled_missing_topic")
        return 0
    due_before = datetime.now(UTC) + timedelta(hours=settings.gmail_watch_renewal_hours)
    async with resources.system_database.session_factory() as session:
        rows = (
            await session.execute(
                select(MailAccount, GmailWatchState)
                .outerjoin(GmailWatchState, GmailWatchState.mail_account_id == MailAccount.id)
                .where(
                    MailAccount.provider == MailProvider.GMAIL,
                    MailAccount.status == AccountStatus.CONNECTED,
                    (
                        GmailWatchState.id.is_(None)
                        | GmailWatchState.expiration_at.is_(None)
                        | (GmailWatchState.expiration_at <= due_before)
                    ),
                )
            )
        ).all()
        alerts = TelegramAlerts(settings, resources.redis)
        renewed = 0
        for account, state in rows:
            try:
                state = await renew_gmail_watch(
                    account=account,
                    state=state,
                    resources=resources,
                    settings=settings,
                )
                session.add(state)
                await alerts.account_recovered(account)
                renewed += 1
            except GmailReauthRequired as error:
                mark_reauth_required(account, str(error))
                if state is None:
                    state = GmailWatchState(
                        tenant_id=account.tenant_id,
                        mail_account_id=account.id,
                    )
                    session.add(state)
                state.status = "reauth_required"
                state.last_error = str(error)
                await alerts.account_issue(account, str(error))
                logger.warning("gmail_watch_reauthorization_required", account_id=str(account.id))
            except Exception as error:
                if state is None:
                    state = GmailWatchState(
                        tenant_id=account.tenant_id,
                        mail_account_id=account.id,
                    )
                    session.add(state)
                state.status = "error"
                state.last_error = str(error)[:2000]
                await alerts.account_issue(account, f"Gmail watch renewal failed: {error}")
                logger.warning(
                    "gmail_watch_renewal_failed",
                    account_id=str(account.id),
                    error_type=type(error).__name__,
                )
        await session.commit()
        return renewed
