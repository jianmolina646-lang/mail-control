from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import database_session
from mail_control.api.identity import client_metadata, identity_service, set_refresh_cookie
from mail_control.modules.identity.service import AuthenticationError
from mail_control.settings import Settings, get_settings

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
Provider = Literal["google", "microsoft"]


class OAuthStartRequest(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class TicketRequest(BaseModel):
    ticket: str = Field(min_length=32, max_length=200)


class RecoveryRequest(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized.count("@") != 1 or any(character.isspace() for character in normalized):
            raise ValueError("invalid email address")
        local, domain = normalized.rsplit("@", 1)
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("invalid email address")
        return normalized


class RecoveryConfirm(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RecoveryRequest.normalize_email(value)


def provider_config(provider: Provider, settings: Settings) -> tuple[str, str, str, str]:
    if provider == "google":
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google login is not configured")
        return settings.google_client_id, settings.google_client_secret, settings.google_login_redirect_uri, "openid email profile"
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Microsoft login is not configured")
    return settings.microsoft_client_id, settings.microsoft_client_secret, settings.microsoft_login_redirect_uri, "openid email profile User.Read"


@router.post("/oauth/{provider}/authorize", response_model=AuthorizationUrlResponse)
async def oauth_authorize(provider: Provider, data: OAuthStartRequest, request: Request) -> AuthorizationUrlResponse:
    settings = get_settings()
    client_id, _, redirect_uri, scope = provider_config(provider, settings)
    state = secrets.token_urlsafe(32)
    await request.app.state.resources.redis.setex(f"login:oauth:{state}", 600, json.dumps({"provider": provider, "tenant_slug": data.tenant_slug}))
    base = "https://accounts.google.com/o/oauth2/v2/auth" if provider == "google" else "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": scope, "state": state, "prompt": "select_account"}
    return AuthorizationUrlResponse(authorization_url=f"{base}?{urlencode(params)}")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: Provider, code: str, state: str, request: Request, session: Annotated[AsyncSession, Depends(database_session)]) -> RedirectResponse:
    settings = get_settings()
    raw = await request.app.state.resources.redis.getdel(f"login:oauth:{state}")
    if not raw:
        return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=expired")
    payload = json.loads(raw)
    if payload.get("provider") != provider:
        return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=invalid")
    client_id, client_secret, redirect_uri, _ = provider_config(provider, settings)
    token_url = "https://oauth2.googleapis.com/token" if provider == "google" else "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(token_url, data={"client_id": client_id, "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
        if token_response.is_error:
            return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=exchange")
        access_token = token_response.json().get("access_token", "")
        user_url = "https://openidconnect.googleapis.com/v1/userinfo" if provider == "google" else "https://graph.microsoft.com/oidc/userinfo"
        user_response = await client.get(user_url, headers={"Authorization": f"Bearer {access_token}"})
    if user_response.is_error:
        return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=profile")
    profile = user_response.json()
    email = str(profile.get("email") or profile.get("preferred_username") or "").strip().casefold()
    if not email or (provider == "google" and profile.get("email_verified") is not True):
        return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=email")
    user_agent, ip_address = client_metadata(request)
    try:
        tokens = await identity_service(session).login_external(payload["tenant_slug"], email, user_agent=user_agent, ip_address=ip_address)
    except AuthenticationError:
        return RedirectResponse(f"{settings.frontend_url}/login?oauth_error=unauthorized")
    ticket = secrets.token_urlsafe(40)
    await request.app.state.resources.redis.setex(f"login:ticket:{ticket}", 60, tokens.model_dump_json())
    return RedirectResponse(f"{settings.frontend_url}/login?ticket={ticket}")


@router.post("/oauth/exchange")
async def oauth_exchange(data: TicketRequest, request: Request, response: Response):
    raw = await request.app.state.resources.redis.getdel(f"login:ticket:{data.ticket}")
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired login ticket")
    payload = json.loads(raw)
    set_refresh_cookie(response, payload["refresh_token"])
    payload.pop("refresh_token", None)
    return payload


def code_digest(settings: Settings, tenant_slug: str, email: str, code: str) -> str:
    return hmac.new(settings.app_secret_key.encode(), f"{tenant_slug}|{email}|{code}".encode(), hashlib.sha256).hexdigest()


def send_recovery_email(settings: Settings, recipient: str, code: str) -> None:
    if not all((settings.smtp_host, settings.smtp_username, settings.smtp_password)):
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "Código para cambiar tu contraseña · Mail Control"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = recipient
    message.set_content(f"Tu código de recuperación es: {code}\n\nCaduca en 10 minutos y solo puede utilizarse una vez.\nSi no solicitaste este cambio, ignora este mensaje.")
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls(context=context)
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


@router.post("/password/request", status_code=status.HTTP_202_ACCEPTED)
async def password_request(data: RecoveryRequest, request: Request, session: Annotated[AsyncSession, Depends(database_session)]):
    settings = get_settings()
    tenant = await identity_service(session).repository.tenant_by_slug(data.tenant_slug)
    user = None
    if tenant is not None:
        from mail_control.infrastructure.database.tenant import set_tenant_context
        await set_tenant_context(session, tenant.id)
        user = await identity_service(session).repository.user_by_email(tenant.id, data.email)
    if user and user.is_active:
        code = f"{secrets.randbelow(1_000_000):06d}"
        key = f"password:reset:{data.tenant_slug}:{data.email.strip().casefold()}"
        await request.app.state.resources.redis.setex(key, 600, json.dumps({"digest": code_digest(settings, data.tenant_slug, data.email.strip().casefold(), code), "attempts": 0}))
        await asyncio.to_thread(send_recovery_email, settings, user.email, code)
    return {"detail": "If the account exists, a recovery code was sent."}


@router.post("/password/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def password_confirm(data: RecoveryConfirm, request: Request, session: Annotated[AsyncSession, Depends(database_session)]):
    settings = get_settings()
    email = data.email.strip().casefold()
    key = f"password:reset:{data.tenant_slug}:{email}"
    raw = await request.app.state.resources.redis.get(key)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired recovery code")
    challenge = json.loads(raw)
    challenge["attempts"] = int(challenge.get("attempts", 0)) + 1
    if challenge["attempts"] > 5:
        await request.app.state.resources.redis.delete(key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired recovery code")
    await request.app.state.resources.redis.setex(key, 600, json.dumps(challenge))
    expected = code_digest(settings, data.tenant_slug, email, data.code)
    if not hmac.compare_digest(expected, challenge["digest"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired recovery code")
    try:
        await identity_service(session).reset_password(data.tenant_slug, email, data.password)
    except AuthenticationError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid recovery request") from error
    await request.app.state.resources.redis.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
