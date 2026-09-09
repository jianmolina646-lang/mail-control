from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, current_principal, database_session
from mail_control.modules.system.mail_freshness import MailSyncHealth, account_health_rows
from mail_control.settings import get_settings

router = APIRouter(prefix="/v1/mail", tags=["mail-health"])


@router.get("/sync-health", response_model=MailSyncHealth)
async def sync_health(
    principal: Annotated[Principal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(database_session)],
) -> MailSyncHealth:
    settings = get_settings()
    rows = await account_health_rows(session, settings, tenant_id=principal.claims.tenant_id)
    accounts = [health for _, health in rows]
    return MailSyncHealth(
        observed_at=datetime.now(UTC),
        stale_after_seconds=settings.mail_sync_stale_after_seconds,
        total_accounts=len(accounts),
        attention_accounts=sum(bool(item.issue) for item in accounts),
        accounts=accounts,
    )
