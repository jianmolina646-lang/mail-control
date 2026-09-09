from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from uuid import UUID

import structlog
from aio_pika.abc import AbstractIncomingMessage
from redis.exceptions import LockError

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.gmail import (
    GmailClient,
    GmailError,
    GmailReauthRequired,
)
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.sync import GmailSyncService
from mail_control.modules.mail.token_manager import AccountUnavailableError, provider_client
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings, get_settings

logger = structlog.get_logger(__name__)
REAUTH_REQUIRED_MESSAGE = "Google authorization expired; reconnect this Gmail account"


def mark_reauth_required(
    account: MailAccount,
    detail: str = REAUTH_REQUIRED_MESSAGE,
) -> None:
    account.status = AccountStatus.REAUTH_REQUIRED
    account.last_error = detail
    account.encrypted_access_token = None
    account.access_token_expires_at = None


async def process_message(
    message: AbstractIncomingMessage,
    resources: Resources,
    settings: Settings,
) -> None:
    # Retry one transient provider/database failure automatically. A redelivered
    # message is rejected on a second failure to avoid an infinite hot loop.
    async with message.process(requeue=not message.redelivered):
        payload = json.loads(message.body)
        tenant_id = UUID(payload["tenant_id"])
        account_id = UUID(payload["mail_account_id"])
        async for session in resources.database.session():
            await set_tenant_context(session, tenant_id)
            repository = MailRepository(session)
            account = await repository.account_by_id(tenant_id, account_id, MailProvider.GMAIL)
            if (
                account is None or account.provider is not MailProvider.GMAIL
                or account.status in {AccountStatus.DISCONNECTED, AccountStatus.REAUTH_REQUIRED}
            ):
                return
            try:
                client = await provider_client(account, session, resources, settings)
                assert isinstance(client, GmailClient)
            except AccountUnavailableError:
                return
            except GmailReauthRequired as error:
                mark_reauth_required(account, str(error))
                await repository.commit()
                await TelegramAlerts(settings, resources.redis).account_issue(
                    account,
                    str(error),
                )
                logger.warning("gmail_reauthorization_required", account_id=str(account.id))
                return
            except GmailError as error:
                account.status = AccountStatus.ERROR
                account.last_error = str(error)
                await repository.commit()
                await TelegramAlerts(settings, resources.redis).account_issue(
                    account,
                    str(error),
                )
                raise
            alerts = TelegramAlerts(settings, resources.redis)
            try:
                await GmailSyncService(repository).synchronize(account, client)
            except GmailReauthRequired as error:
                await set_tenant_context(session, tenant_id)
                mark_reauth_required(account, str(error))
                await repository.commit()
                await alerts.account_issue(account, str(error))
                return
            except Exception as error:
                await alerts.account_issue(account, str(error))
                raise
            await alerts.account_recovered(account)


async def run() -> None:
    settings = get_settings()
    resources = await Resources.connect(settings)
    try:
        channel = await resources.rabbitmq.channel()
        await channel.set_qos(prefetch_count=4)
        queue = await channel.declare_queue("mail.sync.gmail", durable=True)

        async def handler(message: AbstractIncomingMessage) -> None:
            payload = json.loads(message.body)
            account_id = UUID(payload["mail_account_id"])
            lock = resources.redis.lock(
                f"sync:gmail:{account_id}",
                timeout=7200,
                blocking_timeout=0,
            )
            if not await lock.acquire(blocking=False):
                # Another delivery is already synchronizing this same account.
                # This message is a duplicate, so acknowledge it without starting
                # a second full import that would contend for the same records.
                await message.ack()
                return
            try:
                try:
                    await process_message(message, resources, settings)
                except Exception as error:
                    # ``message.process`` has already requeued or rejected the
                    # delivery. Keep the consumer callback from leaking an
                    # unhandled task exception into aio-pika's event loop.
                    logger.warning(
                        "gmail_sync_delivery_failed",
                        account_id=str(account_id),
                        redelivered=message.redelivered,
                        error_type=type(error).__name__,
                    )
            finally:
                with suppress(LockError):
                    await lock.release()

        await queue.consume(handler)
        await asyncio.Future()
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(run())
