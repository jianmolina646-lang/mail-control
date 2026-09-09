"""Serialize OAuth refreshes across sync, watch renewal, and authenticated reads."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime, timedelta

from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.infrastructure.resources import Resources
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.gmail import GmailClient, GmailOAuth, GoogleTokens
from mail_control.modules.mail.microsoft import (
    MicrosoftGraphClient,
    MicrosoftOAuth,
    MicrosoftTokens,
)
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.settings import Settings


class AccountUnavailableError(ValueError):
    """The requested connection no longer has an active grant."""


class AccountTokenManager:
    def __init__(
        self, account: MailAccount, session: AsyncSession,
        resources: Resources, settings: Settings,
    ) -> None:
        self.account = account
        self.session = session
        self.resources = resources
        self.settings = settings
        self.cipher = CredentialCipher(
            settings.credential_encryption_key or settings.app_secret_key
        )

    async def access_token(self, rejected_token: str | None = None) -> str:
        account = self.account
        lock = self.resources.redis.lock(
            f"oauth:refresh:{account.tenant_id}:{account.id}", timeout=90,
            blocking_timeout=30,
        )
        if not await lock.acquire():
            raise RuntimeError("Account token refresh is busy; retry shortly")
        try:
            # Read committed credentials after acquiring the shared lock. The
            # account object may predate a refresh by another process.
            await self.session.refresh(account, attribute_names=[
                "encrypted_access_token", "encrypted_refresh_token",
                "access_token_expires_at", "status",
            ])
            if account.status in {AccountStatus.DISCONNECTED, AccountStatus.REAUTH_REQUIRED}:
                raise AccountUnavailableError("Reconnect or resume this mail account")
            if not account.encrypted_refresh_token:
                raise AccountUnavailableError("The account has no refresh grant")
            current = (
                self.cipher.decrypt(account.encrypted_access_token)
                if account.encrypted_access_token else None
            )
            expires = account.access_token_expires_at
            fresh = expires is not None and expires > datetime.now(UTC) + timedelta(minutes=2)
            if current and fresh and (rejected_token is None or current != rejected_token):
                return current
            tokens = await self._refresh(self.cipher.decrypt(account.encrypted_refresh_token))
            account.encrypted_access_token = self.cipher.encrypt(tokens.access_token)
            account.access_token_expires_at = tokens.expires_at
            if tokens.refresh_token:
                account.encrypted_refresh_token = self.cipher.encrypt(tokens.refresh_token)
            # Publish a rotated refresh grant before releasing the shared lock.
            # Partial imports are idempotent; neither synchronizer advances an
            # unfinished page sequence's checkpoint when this commit occurs.
            await self.session.commit()
            await set_tenant_context(self.session, account.tenant_id)
            return tokens.access_token
        finally:
            with suppress(LockError):
                await lock.release()

    async def _refresh(self, refresh_token: str) -> GoogleTokens | MicrosoftTokens:
        settings = self.settings
        if self.account.provider is MailProvider.GMAIL:
            if not settings.google_client_id or not settings.google_client_secret:
                raise RuntimeError("Gmail OAuth is not configured")
            return await GmailOAuth(
                self.resources.redis, client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                redirect_uri=settings.google_redirect_uri,
            ).refresh_access_token(refresh_token)
        if self.account.provider is MailProvider.MICROSOFT:
            if not settings.microsoft_client_id or not settings.microsoft_client_secret:
                raise RuntimeError("Microsoft OAuth is not configured")
            return await MicrosoftOAuth(
                self.resources.redis, client_id=settings.microsoft_client_id,
                client_secret=settings.microsoft_client_secret,
                redirect_uri=settings.microsoft_redirect_uri,
            ).refresh_access_token(refresh_token)
        raise ValueError("Unsupported mail provider")


async def provider_client(
    account: MailAccount, session: AsyncSession, resources: Resources, settings: Settings,
) -> GmailClient | MicrosoftGraphClient:
    manager = AccountTokenManager(account, session, resources, settings)
    token = await manager.access_token()
    if account.provider is MailProvider.GMAIL:
        return GmailClient(token, refresh_access_token=manager.access_token)
    if account.provider is MailProvider.MICROSOFT:
        return MicrosoftGraphClient(
            token, refresh_access_token=manager.access_token,
            folder_cache=resources.redis,
            folder_cache_key=f"mail:folder-map:{account.tenant_id}:{account.id}",
        )
    raise ValueError("Unsupported mail provider")
