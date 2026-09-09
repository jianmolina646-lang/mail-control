"""Browser-bound mailbox authorization, independent from application login."""

from __future__ import annotations

import hashlib
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import ROLE_RANK
from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.identity.models import RoleName, Tenant, TenantStatus
from mail_control.modules.identity.repository import IdentityRepository
from mail_control.modules.mail.models import MailAccount, MailProvider
from mail_control.modules.mail.repository import MailRepository
from mail_control.settings import Settings


class MailOAuthFailure(ValueError):
    """A public, non-sensitive error code suitable for a redirect."""


def cookie_name(provider: MailProvider, state: str) -> str:
    digest = hashlib.sha256(state.encode()).hexdigest()[:20]
    return f"mc_mail_oauth_{provider.value}_{digest}"


def bind_browser(
    response: Response,
    provider: MailProvider,
    url: str,
    nonce: str,
    settings: Settings,
) -> None:
    state = parse_qs(urlsplit(url).query)["state"][0]
    response.set_cookie(
        cookie_name(provider, state),
        nonce,
        max_age=600,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=f"/v1/providers/{provider.value}/callback",
    )
    response.headers["Cache-Control"] = "no-store"


def finish_redirect(
    settings: Settings,
    provider: MailProvider,
    state: str | None,
    *,
    error: str | None = None,
) -> RedirectResponse:
    query = {"oauth_error": error} if error else {"connected": provider.value}
    response = RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}/cuentas?{urlencode(query)}",
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    if state:
        response.delete_cookie(
            cookie_name(provider, state),
            path=f"/v1/providers/{provider.value}/callback",
            secure=settings.is_production,
            httponly=True,
            samesite="lax",
        )
    return response


async def target_account(
    session: AsyncSession,
    tenant_id: UUID,
    account_id: UUID | None,
    provider: MailProvider,
) -> MailAccount | None:
    if account_id is None:
        return None
    await set_tenant_context(session, tenant_id)
    account = await MailRepository(session).account_by_id(tenant_id, account_id)
    if account is None or account.provider is not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mail account not found")
    return account


async def validate_callback_actor(
    request: Request,
    session: AsyncSession,
    *,
    provider: MailProvider,
    state: str,
    nonce: str | None,
    tenant_id: UUID,
    user_id: UUID,
) -> None:
    supplied = request.cookies.get(cookie_name(provider, state), "")
    if not nonce or not supplied or not secrets.compare_digest(supplied, nonce):
        raise MailOAuthFailure("browser_mismatch")
    await set_tenant_context(session, tenant_id)
    user = await IdentityRepository(session).user_by_id(tenant_id, user_id)
    tenant_status = await session.scalar(select(Tenant.status).where(Tenant.id == tenant_id))
    if (
        user is None
        or not user.is_active
        or ROLE_RANK[user.role] < ROLE_RANK[RoleName.OPERATOR]
        or tenant_status is not TenantStatus.ACTIVE
    ):
        raise MailOAuthFailure("permission_changed")


async def validate_target_identity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID | None,
    provider: MailProvider,
    provider_account_id: str,
) -> None:
    if account_id is None:
        return
    try:
        account = await target_account(session, tenant_id, account_id, provider)
    except HTTPException as error:
        raise MailOAuthFailure("account_unavailable") from error
    if account is None or account.provider_account_id.casefold() != provider_account_id.casefold():
        raise MailOAuthFailure("account_mismatch")
