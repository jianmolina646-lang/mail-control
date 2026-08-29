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
from mail_control.modules.mail.microsoft import MicrosoftError, MicrosoftOAuth
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.schemas import AuthorizationUrlResponse
from mail_control.modules.mail.service import MailAccountService
from mail_control.settings import Settings, get_settings

router = APIRouter(prefix="/v1/providers/microsoft", tags=["microsoft"])
OperatorPrincipal = Annotated[Principal, Depends(require_role(RoleName.OPERATOR))]


def configured_oauth(request: Request, settings: Settings) -> MicrosoftOAuth:
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Microsoft OAuth is not configured",
        )
    return MicrosoftOAuth(
        request.app.state.resources.redis,
        client_id=settings.microsoft_client_id,
        client_secret=settings.microsoft_client_secret,
        redirect_uri=settings.microsoft_redirect_uri,
    )


async def enqueue(request: Request, tenant_id: UUID, account_id: UUID) -> None:
    channel = await request.app.state.resources.rabbitmq.channel()
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(
                    {"tenant_id": str(tenant_id), "mail_account_id": str(account_id)}
                ).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="mail.sync.microsoft",
        )
    finally:
        await channel.close()


@router.post("/authorize", response_model=AuthorizationUrlResponse)
async def authorize(
    request: Request,
    principal: OperatorPrincipal,
) -> AuthorizationUrlResponse:
    url = await configured_oauth(request, get_settings()).authorization_url(
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
        account = await service.connect_microsoft(
            tenant_id=oauth_state.tenant_id,
            user_id=oauth_state.user_id,
            profile=await service.microsoft_profile(tokens),
            tokens=tokens,
        )
    except (MicrosoftError, ValueError) as error:
        await session.rollback()
        if str(error) == "invalid or expired OAuth state":
            return RedirectResponse(
                f"{settings.frontend_url.rstrip('/')}/cuentas?oauth_error=microsoft_state_expired",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    await enqueue(request, account.tenant_id, account.id)
    return RedirectResponse(
        f"{settings.frontend_url.rstrip('/')}/cuentas?connected=microsoft",
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
    await enqueue(request, account.tenant_id, account.id)
    return {"status": "queued"}
