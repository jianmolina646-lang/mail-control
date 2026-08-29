from __future__ import annotations

import asyncio
import json

import aio_pika
from sqlalchemy import select

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.models import MailAccount, MailProvider
from mail_control.settings import get_settings


async def main() -> None:
    resources = await Resources.connect(get_settings())
    queued = 0
    try:
        async for session in resources.database.session():
            accounts = list(
                (
                    await session.scalars(
                        select(MailAccount).where(
                            MailAccount.provider == MailProvider.MICROSOFT
                        )
                    )
                ).all()
            )
            channel = await resources.rabbitmq.channel()
            try:
                for account in accounts:
                    await channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(
                                {
                                    "tenant_id": str(account.tenant_id),
                                    "mail_account_id": str(account.id),
                                }
                            ).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key="mail.sync.microsoft",
                    )
                    queued += 1
            finally:
                await channel.close()
    finally:
        await resources.close()
    print(f"MICROSOFT_SYNCS_QUEUED={queued}")


if __name__ == "__main__":
    asyncio.run(main())
