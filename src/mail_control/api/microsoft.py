from __future__ import annotations

import json
import secrets
from typing import Annotated
from uuid import UUID

import aio_pika
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, database_session, require_role
from mail_control.api.mail_oauth import (
    MailOAuthFailure,
    bind_browser,
    finish_redirect,
    target_account,
    validate_callback_actor,
    validate_target_identity,
)
from mail_control.modules.identity.models import RoleName
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.microsoft import MicrosoftError, MicrosoftOAuth
from mail_control.modules.mail.models import AccountStatus, MailProvider
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.schemas import AuthorizationRequest, AuthorizationUrlResponse
from mail_control.modules.mail.service import MailAccountService
from mail_control.settings import Settings, get_settings

router = APIRouter(prefix="/v1/providers/microsoft", tags=["microsoft"])
OperatorPrincipal = Annotated[Principal, Depends(require_role(RoleName.OPERATOR))]
logger = structlog.get_logger(__name__)


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
    response: Response,
    session: Annotated[AsyncSession, Depends(database_session)],
    payload: AuthorizationRequest | None = None,
) -> AuthorizationUrlResponse:
    settings = get_settings()
    account = await target_account(
        session,
        principal.claims.tenant_id,
        payload.account_id if payload else None,
        MailProvider.MICROSOFT,
    )
    nonce = secrets.token_urlsafe(32)
    url = await configured_oauth(request, settings).authorization_url(
        principal.claims.tenant_id,
        principal.claims.user_id,
        account_id=account.id if account else None,
        email_hint=account.email if account else None,
        browser_nonce=nonce,
    )
    bind_browser(response, MailProvider.MICROSOFT, url, nonce, settings)
    return AuthorizationUrlResponse(authorization_url=url)


@router.get("/callback", response_class=RedirectResponse)
async def callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(database_session)],
    state: Annotated[str | None, Query(max_length=2048)] = None,
    code: Annotated[str | None, Query(max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=300)] = None,
) -> RedirectResponse:
    settings = get_settings()
    oauth = configured_oauth(request, settings)
    try:
        if not state:
            raise MailOAuthFailure("state_expired")
        oauth_state = await oauth.consume_state(state)
        await validate_callback_actor(
            request,
            session,
            provider=MailProvider.MICROSOFT,
            state=state,
            nonce=oauth_state.browser_nonce,
            tenant_id=oauth_state.tenant_id,
            user_id=oauth_state.user_id,
        )
        if error or not code:
            raise MailOAuthFailure(
                "cancelled" if error == "access_denied" else "authorization_failed"
            )
        tokens = await oauth.exchange_code(code, oauth_state.verifier)
        service = MailAccountService(
            MailRepository(session),
            CredentialCipher(settings.credential_encryption_key or settings.app_secret_key),
        )
        profile = await service.microsoft_profile(tokens)
        await validate_target_identity(
            session,
            tenant_id=oauth_state.tenant_id,
            account_id=oauth_state.target_account_id,
            provider=MailProvider.MICROSOFT,
            provider_account_id=str(profile.get("id", "")),
        )
        account = await service.connect_microsoft(
            tenant_id=oauth_state.tenant_id,
            user_id=oauth_state.user_id,
            profile=profile,
            tokens=tokens,
        )
    except (MicrosoftError, ValueError, httpx.HTTPError) as failure:
        await session.rollback()
        reason = str(failure) if isinstance(failure, MailOAuthFailure) else "authorization_failed"
        if isinstance(failure, MicrosoftError) and str(failure) == "invalid or expired OAuth state":
            reason = "state_expired"
        logger.warning("mail_oauth_failed", provider="microsoft", error_type=type(failure).__name__)
        return finish_redirect(settings, MailProvider.MICROSOFT, state, error=reason)
    try:
        await enqueue(request, account.tenant_id, account.id)
    except Exception as failure:
        logger.warning("mail_initial_sync_deferred", error_type=type(failure).__name__)
    return finish_redirect(settings, MailProvider.MICROSOFT, state)


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
    if account is None or account.provider is not MailProvider.MICROSOFT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mail account not found")
    if account.status in (AccountStatus.DISCONNECTED, AccountStatus.REAUTH_REQUIRED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Vuelve a conectar esta cuenta primero.")
    await enqueue(request, account.tenant_id, account.id)
    return {"status": "queued"}
