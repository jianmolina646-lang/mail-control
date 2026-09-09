from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import aio_pika
import structlog
from redis.exceptions import LockError
from sqlalchemy import select

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.gmail_push import renew_due_gmail_watches
from mail_control.modules.mail.microsoft_push import renew_due_microsoft_graph_subscriptions
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.system.mail_freshness import monitor_mail_freshness
from mail_control.settings import get_settings

logger = structlog.get_logger(__name__)
DEFAULT_INTERVAL_SECONDS = 300


def interval_seconds() -> int:
    value = int(os.getenv("AUTO_SYNC_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)))
    return max(60, value)


async def enqueue_due_accounts(resources: Resources, interval: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=interval)
    async with resources.system_database.session_factory() as session:
        accounts = (
            await session.execute(
                select(
                    MailAccount.id,
                    MailAccount.tenant_id,
                    MailAccount.provider,
                ).where(
                    MailAccount.status.in_((AccountStatus.CONNECTED, AccountStatus.ERROR)),
                    (MailAccount.last_synced_at.is_(None) | (MailAccount.last_synced_at <= cutoff)),
                )
            )
        ).all()

    if not accounts:
        return 0

    channel = await resources.rabbitmq.channel()
    try:
        for account_id, tenant_id, provider in accounts:
            routing_key = (
                "mail.sync.gmail" if provider == MailProvider.GMAIL else "mail.sync.microsoft"
            )
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
                routing_key=routing_key,
            )
    finally:
        await channel.close()
    return len(accounts)


async def run() -> None:
    interval = interval_seconds()
    resources = await Resources.connect(get_settings())
    try:
        while True:
            lock = resources.redis.lock(
                "scheduler:automatic-mail-sync",
                timeout=max(interval * 2, 180),
                blocking_timeout=0,
            )
            acquired = await lock.acquire(blocking=False)
            if acquired:
                try:
                    queued = await enqueue_due_accounts(resources, interval)
                    watches_renewed = await renew_due_gmail_watches(resources, get_settings())
                    microsoft_subscriptions_renewed = await renew_due_microsoft_graph_subscriptions(
                        resources,
                        get_settings(),
                    )
                    logger.info("automatic_sync_scheduled", accounts_queued=queued)
                    if watches_renewed:
                        logger.info("gmail_watches_renewed", watches_renewed=watches_renewed)
                    if microsoft_subscriptions_renewed:
                        logger.info(
                            "microsoft_graph_subscriptions_renewed",
                            subscriptions_renewed=microsoft_subscriptions_renewed,
                        )
                except Exception:
                    logger.exception("automatic_sync_schedule_failed")
                finally:
                    try:
                        attention = await monitor_mail_freshness(resources, get_settings())
                        logger.info("mail_freshness_checked", attention_accounts=attention)
                    except Exception:
                        logger.exception("mail_freshness_check_failed")
                    with suppress(LockError):
                        await lock.release()
            await asyncio.sleep(interval)
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(run())
