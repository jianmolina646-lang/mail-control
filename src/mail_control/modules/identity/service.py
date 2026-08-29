from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.identity.models import (
    RefreshSession,
    RoleName,
    Tenant,
    TenantStatus,
    User,
)
from mail_control.modules.identity.repository import IdentityRepository
from mail_control.modules.identity.schemas import (
    LoginRequest,
    RegisterTenantRequest,
    TokenPairResponse,
    UserResponse,
)
from mail_control.modules.identity.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_tenant,
    verify_password,
)
from mail_control.modules.saas.models import Plan, SubscriptionStatus, TenantSubscription
from mail_control.settings import Settings


class IdentityError(Exception):
    pass


class ConflictError(IdentityError):
    pass


class AuthenticationError(IdentityError):
    pass


def session_absolute_deadline(settings: Settings, started_at: datetime) -> datetime:
    return started_at + timedelta(hours=settings.session_absolute_hours)


def session_refresh_deadline(
    settings: Settings,
    *,
    now: datetime,
    started_at: datetime,
) -> datetime:
    idle_deadline = now + timedelta(minutes=settings.session_idle_minutes)
    return min(idle_deadline, session_absolute_deadline(settings, started_at))


class IdentityService:
    def __init__(self, repository: IdentityRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def register(self, data: RegisterTenantRequest) -> TokenPairResponse:
        if await self.repository.tenant_by_slug(data.tenant_slug):
            raise ConflictError("tenant slug is already registered")

        tenant = Tenant(name=data.tenant_name.strip(), slug=data.tenant_slug)
        self.repository.add(tenant)
        await self.repository.flush()
        await set_tenant_context(self.repository.session, tenant.id)

        owner = User(
            tenant_id=tenant.id,
            email=data.email,
            email_normalized=data.email.casefold(),
            display_name=data.owner_name.strip(),
            password_hash=hash_password(data.password),
            role=RoleName.OWNER,
        )
        self.repository.add(owner)
        await self.repository.flush()
        starter = await self.repository.session.scalar(select(Plan).where(Plan.code == "starter"))
        if starter is None:
            raise IdentityError("starter plan is not configured")
        now = datetime.now(UTC)
        self.repository.session.add(
            TenantSubscription(
                tenant_id=tenant.id,
                plan_id=starter.id,
                status=SubscriptionStatus.TRIALING,
                period_start=now,
                period_end=now + timedelta(days=30),
            )
        )
        response = await self._issue_pair(owner)
        await self.repository.commit()
        return response

    async def login(
        self,
        data: LoginRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPairResponse:
        tenant = await self.repository.tenant_by_slug(data.tenant_slug)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            raise AuthenticationError("invalid credentials")

        await set_tenant_context(self.repository.session, tenant.id)
        user = await self.repository.user_by_email(tenant.id, data.email)
        if user is None or not user.is_active:
            raise AuthenticationError("invalid credentials")
        if not verify_password(user.password_hash, data.password):
            raise AuthenticationError("invalid credentials")

        user.last_login_at = datetime.now(UTC)
        response = await self._issue_pair(
            user,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.repository.commit()
        return response

    async def login_external(
        self,
        tenant_slug: str,
        email: str,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPairResponse:
        tenant = await self.repository.tenant_by_slug(tenant_slug)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            raise AuthenticationError("account is not authorized")
        await set_tenant_context(self.repository.session, tenant.id)
        user = await self.repository.user_by_email(tenant.id, email)
        if user is None or not user.is_active:
            raise AuthenticationError("account is not authorized")
        user.last_login_at = datetime.now(UTC)
        response = await self._issue_pair(user, user_agent=user_agent, ip_address=ip_address)
        await self.repository.commit()
        return response

    async def reset_password(self, tenant_slug: str, email: str, password: str) -> None:
        tenant = await self.repository.tenant_by_slug(tenant_slug)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            raise AuthenticationError("invalid recovery request")
        await set_tenant_context(self.repository.session, tenant.id)
        user = await self.repository.user_by_email(tenant.id, email)
        if user is None or not user.is_active:
            raise AuthenticationError("invalid recovery request")
        user.password_hash = hash_password(password)
        await self.repository.commit()

    async def rotate_refresh_token(
        self,
        refresh_token: str,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPairResponse:
        try:
            tenant_id = refresh_token_tenant(refresh_token)
        except ValueError:
            raise AuthenticationError("invalid refresh token") from None
        await set_tenant_context(self.repository.session, tenant_id)
        session = await self.repository.refresh_session(hash_refresh_token(refresh_token))
        now = datetime.now(UTC)
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
            or session_absolute_deadline(self.settings, session.created_at) <= now
        ):
            raise AuthenticationError("invalid refresh token")

        user = await self.repository.user_by_id(session.tenant_id, session.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("invalid refresh token")

        await self.repository.revoke_session(session, now)
        response = await self._issue_pair(
            user,
            user_agent=user_agent,
            ip_address=ip_address,
            session_started_at=session.created_at,
        )
        await self.repository.commit()
        return response

    async def logout(self, refresh_token: str) -> None:
        try:
            tenant_id = refresh_token_tenant(refresh_token)
        except ValueError:
            return
        await set_tenant_context(self.repository.session, tenant_id)
        session = await self.repository.refresh_session(hash_refresh_token(refresh_token))
        if session is not None and session.revoked_at is None:
            await self.repository.revoke_session(session, datetime.now(UTC))
            await self.repository.commit()

    async def _issue_pair(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
        session_started_at: datetime | None = None,
    ) -> TokenPairResponse:
        access_token, expires_in = create_access_token(
            self.settings,
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )
        refresh_token, token_hash = create_refresh_token(user.tenant_id)
        now = datetime.now(UTC)
        started_at = session_started_at or now
        self.repository.add(
            RefreshSession(
                tenant_id=user.tenant_id,
                user_id=user.id,
                token_hash=token_hash,
                created_at=started_at,
                expires_at=session_refresh_deadline(
                    self.settings,
                    now=now,
                    started_at=started_at,
                ),
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
        )
