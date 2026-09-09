from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import (
    Principal,
    current_principal,
    database_session,
    require_role,
)
from mail_control.modules.analysis.models import RiskLevel
from mail_control.modules.dashboard.cursor import decode_cursor, encode_cursor
from mail_control.modules.dashboard.filters import MessageFilters
from mail_control.modules.dashboard.repository import DashboardRepository
from mail_control.modules.dashboard.schemas import (
    AccountItem,
    AlertPage,
    AnalysisPage,
    DashboardSummary,
    MessageContent,
    MessageCounts,
    MessagePage,
    MessageStateUpdate,
    ThreadPage,
)
from mail_control.modules.identity.models import RoleName
from mail_control.modules.mail.content_service import (
    CONTENT_ERRORS,
    AttachmentNotFound,
    ContentLimitError,
    MessageContentService,
    detected_image_type,
)
from mail_control.modules.mail.image_proxy import ImageProxyError, fetch_image, image_sources
from mail_control.modules.mail.models import EmailMessage, MailAccount
from mail_control.settings import get_settings

router = APIRouter(prefix="/v1", tags=["dashboard"])
AuthenticatedPrincipal = Annotated[Principal, Depends(current_principal)]
OperatorPrincipal = Annotated[Principal, Depends(require_role(RoleName.OPERATOR))]
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


def message_filters(
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    account_id: UUID | None = None,
    provider: Annotated[str | None, Query(max_length=32)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    risk_level: Annotated[str | None, Query(max_length=80)] = None,
    is_read: bool | None = None,
    is_starred: bool | None = None,
    has_attachments: bool | None = None,
    account: Annotated[str | None, Query(max_length=320)] = None,
    sender: Annotated[str | None, Query(max_length=320)] = None,
    recipient: Annotated[str | None, Query(max_length=320)] = None,
    platform: Annotated[str | None, Query(max_length=120)] = None,
    date_from: Annotated[str | None, Query(max_length=40)] = None,
    date_to: Annotated[str | None, Query(max_length=40)] = None,
) -> MessageFilters:
    return MessageFilters(search=search, account_id=account_id, provider=provider,
                          category=category, risk_level=risk_level, is_read=is_read,
                          is_starred=is_starred, has_attachments=has_attachments,
                          account=account, sender=sender, recipient=recipient,
                          platform=platform, date_from=date_from, date_to=date_to)


SearchFilters = Annotated[MessageFilters, Depends(message_filters)]


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
    filters: SearchFilters,
    mailbox: Literal["inbox", "archive", "trash", "sent", "drafts", "spam", "other", "all"]
    = "inbox",
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessagePage:
    try:
        return await DashboardRepository(session, principal.claims.tenant_id).messages(
            search=filters.search,
            account_id=filters.account_id,
            provider=filters.provider,
            category=filters.category,
            risk_level=filters.risk_level,
            mailbox=mailbox,
            cursor=cursor,
            limit=limit,
            filters=filters,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.get("/mail/messages/counts", response_model=MessageCounts)
async def message_counts(
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    filters: SearchFilters,
) -> MessageCounts:
    try:
        return await DashboardRepository(session, principal.claims.tenant_id).message_counts(
            filters
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
            setattr(message, f"local_{field}", value)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _message_account(
    message_id: UUID,
    tenant_id: UUID,
    session: AsyncSession,
    account_id: UUID | None = None,
) -> tuple[EmailMessage, MailAccount]:
    statement = (
        select(EmailMessage, MailAccount)
        .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
        .where(EmailMessage.id == message_id, EmailMessage.tenant_id == tenant_id,
               MailAccount.tenant_id == tenant_id, EmailMessage.deleted_at.is_(None))
    )
    if account_id is not None:
        statement = statement.where(MailAccount.id == account_id)
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found")
    return row[0], row[1]


def _content_service(request: Request, session: AsyncSession) -> MessageContentService:
    return MessageContentService(session, request.app.state.resources, get_settings())


def _content_error(error: Exception) -> HTTPException:
    if isinstance(error, AttachmentNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    if isinstance(error, ContentLimitError):
        return HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error))
    return HTTPException(status.HTTP_502_BAD_GATEWAY,
                         "message content unavailable; retry or reconnect the account")


@router.get("/mail/messages/{message_id}", response_model=MessageContent)
async def message_content(
    message_id: UUID,
    request: Request,
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    account_id: UUID | None = None,
) -> MessageContent:
    message, account = await _message_account(message_id, principal.claims.tenant_id,
                                              session, account_id)
    try:
        return await _content_service(request, session).content(message, account)
    except CONTENT_ERRORS as error:
        raise _content_error(error) from None


@router.get("/mail/messages/{message_id}/thread", response_model=ThreadPage)
async def message_thread(
    message_id: UUID,
    request: Request,
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    account_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ThreadPage:
    anchor, account = await _message_account(message_id, principal.claims.tenant_id,
                                             session, account_id)
    sort_time = func.coalesce(EmailMessage.received_at, EmailMessage.created_at)
    statement = select(EmailMessage).where(
        EmailMessage.tenant_id == principal.claims.tenant_id,
        EmailMessage.mail_account_id == account.id, EmailMessage.deleted_at.is_(None),
        EmailMessage.thread_id == anchor.thread_id if anchor.thread_id
        else EmailMessage.id == anchor.id,
    )
    total_count = int(await session.scalar(select(func.count()).select_from(
        statement.subquery()
    )) or 0)
    if cursor:
        try:
            timestamp, cursor_id = decode_cursor(cursor)
        except ValueError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
        statement = statement.where(or_(sort_time > timestamp,
                                        and_(sort_time == timestamp, EmailMessage.id > cursor_id)))
    rows = list((await session.scalars(statement.order_by(
        sort_time.asc(), EmailMessage.id.asc()
    ).limit(limit + 1))).all())
    visible = rows[:limit]
    service = _content_service(request, session)
    try:
        items = [await service.content(message, account) for message in visible]
    except CONTENT_ERRORS as error:
        raise _content_error(error) from None
    last = visible[-1] if visible else None
    next_cursor = encode_cursor(last.received_at or last.created_at, last.id) if (
        last is not None and len(rows) > limit
    ) else None
    return ThreadPage(items=items, next_cursor=next_cursor, total_count=total_count)


@router.get("/mail/messages/{message_id}/attachments/{attachment_id}")
async def message_attachment(
    message_id: UUID,
    attachment_id: str,
    request: Request,
    principal: AuthenticatedPrincipal,
    session: DatabaseSession,
    account_id: UUID | None = None,
    inline: bool = False,
) -> Response:
    message, account = await _message_account(message_id, principal.claims.tenant_id,
                                              session, account_id)
    if len(attachment_id) > 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    try:
        data, metadata = await _content_service(request, session).download(
            message, account, attachment_id
        )
    except CONTENT_ERRORS as error:
        raise _content_error(error) from None
    media_type = "application/octet-stream"
    disposition = "attachment"
    if inline:
        detected = detected_image_type(data)
        if not metadata.inline_url or detected != metadata.content_type:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                "only verified embedded raster images can be displayed inline")
        disposition, media_type = "inline", detected
    filename = metadata.filename.replace("\r", "").replace("\n", "")[:240]
    return Response(content=data, media_type=media_type, headers={
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename, safe='')}",
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


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
    message, account = await _message_account(message_id, principal.claims.tenant_id, session)
    try:
        html = await _content_service(request, session).html(message, account)
    except CONTENT_ERRORS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image unavailable") from None
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
