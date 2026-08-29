from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from aio_pika.abc import AbstractIncomingMessage
from redis.exceptions import LockError

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.microsoft import (
    MicrosoftError,
    MicrosoftGraphClient,
    MicrosoftOAuth,
    MicrosoftReauthorizationRequired,
    MicrosoftTransientError,
)
from mail_control.modules.mail.microsoft_sync import MicrosoftSyncService
from mail_control.modules.mail.models import AccountStatus, MailProvider
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings, get_settings

logger = structlog.get_logger(__name__)


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
            account = await repository.account_by_id(tenant_id, account_id)
            if (
                account is None
                or account.provider is not MailProvider.MICROSOFT
                or account.status is AccountStatus.DISCONNECTED
            ):
                return
            cipher = CredentialCipher(
                settings.credential_encryption_key or settings.app_secret_key
            )
            token: str
            if (
                account.encrypted_access_token
                and account.access_token_expires_at
                and account.access_token_expires_at
                > datetime.now(UTC) + timedelta(minutes=2)
            ):
                token = cipher.decrypt(account.encrypted_access_token)
            else:
                if not settings.microsoft_client_id or not settings.microsoft_client_secret:
                    raise RuntimeError("Microsoft OAuth is not configured")
                oauth = MicrosoftOAuth(
                    resources.redis,
                    client_id=settings.microsoft_client_id,
                    client_secret=settings.microsoft_client_secret,
                    redirect_uri=settings.microsoft_redirect_uri,
                )
                try:
                    tokens = await oauth.refresh_access_token(
                        cipher.decrypt(account.encrypted_refresh_token)
                    )
                except MicrosoftReauthorizationRequired as error:
                    account.status = AccountStatus.REAUTH_REQUIRED
                    account.last_error = str(error)
                    account.encrypted_access_token = None
                    account.access_token_expires_at = None
                    await repository.commit()
                    await TelegramAlerts(settings, resources.redis).account_issue(
                        account,
                        str(error),
                    )
                    return
                except MicrosoftError as error:
                    account.status = AccountStatus.ERROR
                    account.last_error = str(error)
                    await repository.commit()
                    await TelegramAlerts(settings, resources.redis).account_issue(
                        account,
                        str(error),
                    )
                    raise
                token = tokens.access_token
                account.encrypted_access_token = cipher.encrypt(token)
                account.access_token_expires_at = tokens.expires_at
                if tokens.refresh_token:
                    account.encrypted_refresh_token = cipher.encrypt(tokens.refresh_token)
            alerts = TelegramAlerts(settings, resources.redis)
            try:
                await MicrosoftSyncService(repository).synchronize(
                    account,
                    MicrosoftGraphClient(token),
                )
            except MicrosoftTransientError:
                raise
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
        queue = await channel.declare_queue("mail.sync.microsoft", durable=True)

        async def handler(message: AbstractIncomingMessage) -> None:
            payload = json.loads(message.body)
            account_id = UUID(payload["mail_account_id"])
            lock = resources.redis.lock(
                f"sync:microsoft:{account_id}",
                timeout=7200,
                blocking_timeout=0,
            )
            if not await lock.acquire(blocking=False):
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
                        "microsoft_sync_delivery_failed",
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
