from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

import aio_pika
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, database_session, require_role
from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.identity.models import RoleName
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.gmail import GmailError, GmailOAuth
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.schemas import (
    AuthorizationUrlResponse,
)
from mail_control.modules.mail.service import MailAccountService
from mail_control.settings import Settings, get_settings

router = APIRouter(prefix="/v1/providers/gmail", tags=["gmail"])
OperatorPrincipal = Annotated[Principal, Depends(require_role(RoleName.OPERATOR))]


def configured_oauth(request: Request, settings: Settings) -> GmailOAuth:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Gmail OAuth is not configured",
        )
    return GmailOAuth(
        request.app.state.resources.redis,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )


@router.post("/authorize", response_model=AuthorizationUrlResponse)
async def authorize(
    request: Request,
    principal: OperatorPrincipal,
) -> AuthorizationUrlResponse:
    oauth = configured_oauth(request, get_settings())
    url = await oauth.authorization_url(
        principal.claims.tenant_id,
        principal.claims.user_id,
    )
    return AuthorizationUrlResponse(authorization_url=url)


@router.get("/callback", response_class=RedirectResponse)
async def callback(
    request: Request,
    state: Annotated[str, Query(min_length=16)],
    code: Annotated[str, Query(min_length=4)],
    session: Annotated[AsyncSession, Depends(database_session)],
) -> RedirectResponse:
    settings = get_settings()
    oauth = configured_oauth(request, settings)
    try:
        oauth_state = await oauth.consume_state(state)
        tokens = await oauth.exchange_code(code, oauth_state.verifier)
        await set_tenant_context(session, oauth_state.tenant_id)
        service = MailAccountService(
            MailRepository(session),
            CredentialCipher(settings.credential_encryption_key or settings.app_secret_key),
        )
        profile = await service.profile_for_tokens(tokens)
        account = await service.connect_gmail(
            tenant_id=oauth_state.tenant_id,
            user_id=oauth_state.user_id,
            profile=profile,
            tokens=tokens,
        )
    except (GmailError, ValueError) as error:
        await session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    channel = await request.app.state.resources.rabbitmq.channel()
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(
                    {
                        "tenant_id": str(account.tenant_id),
                        "mail_account_id": str(account.id),
                    }
                ).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="mail.sync.gmail",
        )
    finally:
        await channel.close()
    return RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}/cuentas?connected=gmail",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{account_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def request_sync(
    account_id: UUID,
    request: Request,
    principal: OperatorPrincipal,
    session: Annotated[AsyncSession, Depends(database_session)],
) -> dict[str, str]:
    account = await MailRepository(session).account_by_id(
        principal.claims.tenant_id,
        account_id,
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mail account not found")
    channel = await request.app.state.resources.rabbitmq.channel()
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(
                    {
                        "tenant_id": str(account.tenant_id),
                        "mail_account_id": str(account.id),
                    }
                ).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="mail.sync.gmail",
        )
    finally:
        await channel.close()
    return {"status": "queued"}
