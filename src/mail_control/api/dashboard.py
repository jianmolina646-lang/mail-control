from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import (
    Principal,
    current_principal,
    database_session,
    require_role,
)
from mail_control.modules.analysis.models import RiskLevel
from mail_control.modules.dashboard.repository import DashboardRepository
from mail_control.modules.dashboard.schemas import (
    AccountItem,
    AlertPage,
    AnalysisPage,
    DashboardSummary,
    MessagePage,
    MessageContent,
    MessageStateUpdate,
)
from mail_control.modules.identity.models import RoleName
from mail_control.modules.mail.content import message_body, message_html
from mail_control.modules.mail.image_proxy import ImageProxyError, fetch_image, image_sources
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider

router = APIRouter(prefix="/v1", tags=["dashboard"])
AuthenticatedPrincipal = Annotated[Principal, Depends(current_principal)]
OperatorPrincipal = Annotated[Principal, Depends(require_role(RoleName.OPERATOR))]
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def summary(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
) -> DashboardSummary:
    return await DashboardRepository(session, principal.claims.tenant_id).summary()


@router.get("/mail/accounts", response_model=list[AccountItem])
async def accounts(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
) -> list[AccountItem]:
    return await DashboardRepository(session, principal.claims.tenant_id).accounts()


@router.get("/mail/messages", response_model=MessagePage)
async def messages(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    search: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
    account_id: UUID | None = None,
    provider: MailProvider | None = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    risk_level: RiskLevel | None = None,
    mailbox: Literal["inbox", "archive", "trash"] = "inbox",
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    try:
        return await DashboardRepository(session, principal.claims.tenant_id).messages(
            search=search,
            account_id=account_id,
            provider=provider,
            category=category,
            risk_level=risk_level,
            mailbox=mailbox,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.patch("/mail/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_message_state(
    message_id: UUID,
    payload: MessageStateUpdate,
    principal: OperatorPrincipal,
    session: DatabaseSession,
) -> Response:
    message = await session.scalar(
        select(EmailMessage).where(
            EmailMessage.id == message_id,
            EmailMessage.tenant_id == principal.claims.tenant_id,
            EmailMessage.deleted_at.is_(None),
        )
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    for field in ("is_read", "is_starred", "mailbox"):
        value = getattr(payload, field)
        if value is not None:
            setattr(message, field, value)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mail/messages/{message_id}", response_model=MessageContent)
async def message_content(
    message_id: UUID,
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
) -> MessageContent:
    row = (
        await session.execute(
            select(EmailMessage.payload, EmailMessage.snippet, MailAccount.provider)
            .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
            .where(
                EmailMessage.id == message_id,
                EmailMessage.tenant_id == principal.claims.tenant_id,
                EmailMessage.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    payload, snippet, provider = row
    return MessageContent(
        id=message_id,
        body=message_body(payload, provider, snippet),
        body_html=message_html(payload, provider),
    )


@router.get("/mail/messages/{message_id}/images/{image_index}")
async def message_image(
    message_id: UUID,
    image_index: int,
    request: Request,
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
) -> Response:
    if image_index < 0 or image_index >= 100:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image not found")
    row = (
        await session.execute(
            select(EmailMessage.payload, MailAccount.provider)
            .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
            .where(
                EmailMessage.id == message_id,
                EmailMessage.tenant_id == principal.claims.tenant_id,
                EmailMessage.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    payload, provider = row
    html = message_html(payload, provider)
    sources = image_sources(html or "")
    if image_index >= len(sources):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image not found")
    try:
        content, media_type = await fetch_image(
            request.app.state.resources.redis,
            sources[image_index],
        )
    except (ImageProxyError, httpx.HTTPError, OSError, ValueError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image unavailable") from None
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/alerts", response_model=AlertPage)
async def alerts(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    open_only: bool = True,
    risk_level: RiskLevel | None = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertPage:
    try:
        return await DashboardRepository(session, principal.claims.tenant_id).alerts(
            open_only=open_only,
            risk_level=risk_level,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.get("/analyses", response_model=AnalysisPage)
async def analyses(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    search: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
    message_id: UUID | None = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    risk_level: RiskLevel | None = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AnalysisPage:
    try:
        return await DashboardRepository(session, principal.claims.tenant_id).analyses(
            search=search,
            message_id=message_id,
            category=category,
            risk_level=risk_level,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.get("/analysis/incidents/active", response_model=AnalysisPage)
async def active_payment_incidents(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> AnalysisPage:
    return await DashboardRepository(
        session, principal.claims.tenant_id
    ).active_payment_analyses(limit=limit)


@router.patch("/alerts/{alert_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_alert(
    alert_id: UUID,
    principal: OperatorPrincipal,
    session: DatabaseSession,
) -> Response:
    resolved = await DashboardRepository(
        session,
        principal.claims.tenant_id,
    ).resolve_alert(alert_id)
    if not resolved:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
