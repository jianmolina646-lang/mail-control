from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.models import (
    AccountStatus,
    GmailWatchState,
    MailAccount,
    MailProvider,
    MicrosoftGraphSubscription,
)
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings

Issue = Literal["reauth_required", "sync_error", "never_synced", "stale", "push_expired"]


class AccountSyncHealth(BaseModel):
    account_id: UUID
    provider: MailProvider
    status: AccountStatus
    last_synced_at: datetime | None
    seconds_since_sync: int | None
    issue: Issue | None


class MailSyncHealth(BaseModel):
    observed_at: datetime
    stale_after_seconds: int
    total_accounts: int
    attention_accounts: int
    accounts: list[AccountSyncHealth]


def sync_issue(
    account: MailAccount,
    now: datetime,
    threshold: int,
    *,
    push_enabled: bool = False,
    push_expires_at: datetime | None = None,
) -> Issue | None:
    if account.status is AccountStatus.DISCONNECTED:
        return None
    if account.status is AccountStatus.REAUTH_REQUIRED:
        return "reauth_required"
    if account.status is AccountStatus.ERROR:
        return "sync_error"
    reference = account.last_synced_at or account.created_at
    if reference and (now - reference).total_seconds() > threshold:
        return "stale" if account.last_synced_at else "never_synced"
    if push_enabled and push_expires_at and push_expires_at <= now:
        return "push_expired"
    return None


async def account_health_rows(
    session: AsyncSession,
    settings: Settings,
    *,
    tenant_id: UUID | None = None,
) -> list[tuple[MailAccount, AccountSyncHealth]]:
    statement = (
        select(MailAccount, GmailWatchState.expiration_at, MicrosoftGraphSubscription.expiration_at)
        .outerjoin(GmailWatchState, GmailWatchState.mail_account_id == MailAccount.id)
        .outerjoin(
            MicrosoftGraphSubscription, MicrosoftGraphSubscription.mail_account_id == MailAccount.id
        )
        .where(MailAccount.status != AccountStatus.DISCONNECTED)
        .order_by(MailAccount.id)
    )
    if tenant_id is not None:
        statement = statement.where(MailAccount.tenant_id == tenant_id)
    now = datetime.now(UTC)
    result: list[tuple[MailAccount, AccountSyncHealth]] = []
    for account, gmail_expiry, microsoft_expiry in (await session.execute(statement)).all():
        is_gmail = account.provider is MailProvider.GMAIL
        issue = sync_issue(
            account,
            now,
            settings.mail_sync_stale_after_seconds,
            push_enabled=(
                settings.gmail_push_enabled
                if is_gmail
                else settings.microsoft_graph_webhook_enabled
            ),
            push_expires_at=gmail_expiry if is_gmail else microsoft_expiry,
        )
        result.append(
            (
                account,
                AccountSyncHealth(
                    account_id=account.id,
                    provider=account.provider,
                    status=account.status,
                    last_synced_at=account.last_synced_at,
                    seconds_since_sync=max(0, int((now - account.last_synced_at).total_seconds()))
                    if account.last_synced_at
                    else None,
                    issue=issue,
                ),
            )
        )
    return result


class FreshnessAlerts(TelegramAlerts):
    # Separate incident keys: a successful sync must not clear an expired-push incident.
    def _active_key(self, account: MailAccount) -> str:
        return f"mail-control:telegram-freshness:{account.id}:active"

    def _dedupe_key(self, account: MailAccount, fingerprint: str) -> str:
        return f"mail-control:telegram-freshness:{account.id}:error:{fingerprint}"


ISSUE_TEXT: dict[Issue, str] = {
    "reauth_required": "El proveedor solicita volver a autorizar esta cuenta en el panel.",
    "sync_error": "La última sincronización falló. Revisa el estado de esta cuenta en el panel.",
    "never_synced": "La primera sincronización no terminó dentro del tiempo previsto.",
    "stale": "La cuenta lleva demasiado tiempo sin completar una sincronización.",
    "push_expired": "La notificación de nuevos correos caducó. El sondeo de respaldo sigue activo.",
}


async def monitor_mail_freshness(resources: Resources, settings: Settings) -> int:
    async with resources.system_database.session_factory() as session:
        rows = await account_health_rows(session, settings)
    alerts = FreshnessAlerts(settings, resources.redis)
    issues = 0
    for account, health in rows:
        if health.issue:
            issues += 1
            await alerts.account_issue(account, ISSUE_TEXT[health.issue])
        else:
            await alerts.account_recovered(account)
    return issues
