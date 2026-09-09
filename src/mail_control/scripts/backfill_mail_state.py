"""Backfill one bounded local batch without provider requests or cursor changes."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.database.session import Database
from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.mail.microsoft_sync import microsoft_message_values
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider
from mail_control.modules.mail.sync import message_values
from mail_control.settings import get_settings


@dataclass
class BackfillSummary:
    processed: int = 0
    changed: int = 0
    next_after_id: str | None = None
    applied: bool = False


def state_values(
    account: MailAccount, message: EmailMessage, folder_mailboxes: dict[str, str] | None = None,
) -> dict[str, object]:
    if account.provider is MailProvider.GMAIL:
        values = message_values(account, message.payload)
    else:
        if folder_mailboxes is None:
            raise ValueError("Run a Microsoft sync first to populate its cached folder map")
        values = microsoft_message_values(account, message.payload, folder_mailboxes)
    result: dict[str, object] = {"provider_folder_id": values["provider_folder_id"]}
    for field in ("is_read", "is_starred", "mailbox"):
        remote = values[f"provider_{field}"]
        override = getattr(message, f"local_{field}")
        result[f"provider_{field}"] = remote
        result[field] = override if override is not None else remote
    return result


async def backfill_batch(
    session: AsyncSession, account: MailAccount, *, limit: int = 200,
    after_id: UUID | None = None, apply: bool = False,
    folder_mailboxes: dict[str, str] | None = None,
) -> BackfillSummary:
    if not 1 <= limit <= 1000:
        raise ValueError("Batch limit must be between 1 and 1000")
    statement = select(EmailMessage).where(
        EmailMessage.tenant_id == account.tenant_id,
        EmailMessage.mail_account_id == account.id,
    ).order_by(EmailMessage.id).limit(limit)
    if after_id is not None:
        statement = statement.where(EmailMessage.id > after_id)
    # Lock rows before deriving values so a concurrent sync cannot be overwritten
    # with an older payload. No skip_locked: continuation must not skip rows.
    if apply:
        statement = statement.with_for_update()
    rows = (await session.scalars(statement)).all()
    summary = BackfillSummary(applied=apply)
    for message in rows:
        values = state_values(account, message, folder_mailboxes)
        changed = any(getattr(message, key) != value for key, value in values.items())
        if apply and changed:
            for key, value in values.items():
                setattr(message, key, value)
        summary.processed += 1
        summary.changed += int(changed)
        summary.next_after_id = str(message.id)
    if apply:
        await session.commit()
    return summary


async def run(
    tenant_id: UUID, account_id: UUID, *, limit: int, after_id: UUID | None, apply: bool,
) -> BackfillSummary:
    settings = get_settings()
    database = Database(settings.database_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with database.session_factory() as session:
            await set_tenant_context(session, tenant_id)
            account = await session.scalar(select(MailAccount).where(
                MailAccount.tenant_id == tenant_id, MailAccount.id == account_id,
            ))
            if account is None:
                raise ValueError("Account not found in the selected tenant")
            folder_map: dict[str, str] | None = None
            if account.provider is MailProvider.MICROSOFT:
                raw = await redis.get(f"mail:folder-map:{tenant_id}:{account_id}")
                parsed = json.loads(raw) if raw else None
                if not isinstance(parsed, dict) or not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in parsed.items()
                ):
                    raise ValueError("Run one Microsoft sync before this local backfill")
                folder_map = cast(dict[str, str], parsed)
            return await backfill_batch(
                session, account, limit=limit, after_id=after_id,
                apply=apply, folder_mailboxes=folder_map,
            )
    finally:
        await redis.aclose()
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--account-id", type=UUID, required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--after-id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    summary = asyncio.run(run(
        args.tenant_id, args.account_id, limit=args.limit,
        after_id=args.after_id, apply=args.apply,
    ))
    print(json.dumps(asdict(summary)))


if __name__ == "__main__":
    main()
