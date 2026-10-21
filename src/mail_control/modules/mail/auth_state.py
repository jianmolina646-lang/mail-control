"""Conditional account writes: an older operation must not replace a new grant."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Table, inspect, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from mail_control.modules.mail.models import AccountStatus, MailAccount

AUTH_STATE_FIELDS = (
    "encrypted_refresh_token", "encrypted_access_token", "access_token_expires_at",
    "status", "last_error", "last_synced_at", "history_cursor",
)


class AccountAuthorizationChanged(ValueError):
    """A newer authorization or a paused account superseded this operation."""


async def update_account_if_current(
    session: AsyncSession, account: MailAccount, expected_grant: str,
    values: dict[str, Any],
) -> bool:
    # No ORM autoflush may write stale fields before the conditional UPDATE.
    # Reset dirty account fields so a later commit cannot bypass this guard.
    with session.no_autoflush:
        state = inspect(account)
        for name in AUTH_STATE_FIELDS:
            history = state.attrs[name].history
            if history.has_changes():
                previous = history.deleted[0] if history.deleted else None
                set_committed_value(account, name, previous)
        allowed = [AccountStatus.CONNECTED, AccountStatus.SYNCING, AccountStatus.ERROR]
        if values.get("status") == AccountStatus.REAUTH_REQUIRED:
            allowed.append(AccountStatus.REAUTH_REQUIRED)
        result = await session.execute(
            update(cast(Table, MailAccount.__table__)).where(
                MailAccount.id == account.id,
                MailAccount.tenant_id == account.tenant_id,
                MailAccount.encrypted_refresh_token == expected_grant,
                MailAccount.status.in_(allowed),
            ).values(**values)
        )
        if result.rowcount == 1:
            for name, value in values.items():
                set_committed_value(account, name, value)
            return True
        await session.refresh(account, attribute_names=list(AUTH_STATE_FIELDS))
        return False


async def mark_reauth_if_current(
    session: AsyncSession, account: MailAccount, error: Exception,
) -> bool:
    expected = getattr(error, "_mail_expected_grant", account.encrypted_refresh_token)
    return await update_account_if_current(session, account, expected, {
        "status": AccountStatus.REAUTH_REQUIRED, "last_error": str(error)[:2000],
        "encrypted_access_token": None, "access_token_expires_at": None,
    })
