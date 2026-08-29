from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider, SyncRun
from mail_control.settings import get_settings


async def main() -> None:
    resources = await Resources.connect(get_settings())
    try:
        async for session in resources.database.session():
            account = await session.scalar(
                select(MailAccount).where(MailAccount.provider == MailProvider.MICROSOFT)
            )
            if account is None:
                print("account_found=False")
                return
            message_count = await session.scalar(
                select(func.count(EmailMessage.id)).where(
                    EmailMessage.mail_account_id == account.id
                )
            )
            latest_run = await session.scalar(
                select(SyncRun)
                .where(SyncRun.mail_account_id == account.id)
                .order_by(SyncRun.started_at.desc())
                .limit(1)
            )
            print("account_found=True")
            print(f"account_status={account.status.value}")
            print(f"last_synced={account.last_synced_at is not None}")
            print(f"has_error={bool(account.last_error)}")
            print(f"message_count={message_count or 0}")
            print(f"latest_run={latest_run.status.value if latest_run else 'none'}")
            if latest_run:
                print(f"messages_seen={latest_run.messages_seen}")
                print(f"messages_created={latest_run.messages_created}")
    finally:
        await resources.close()


if __name__ == "__main__":
    asyncio.run(main())
