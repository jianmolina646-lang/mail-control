from __future__ import annotations

from uuid import UUID

from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.gmail import GmailClient, GoogleTokens
from mail_control.modules.mail.microsoft import MicrosoftGraphClient, MicrosoftTokens
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.mail.repository import MailRepository


class MailAccountService:
    def __init__(self, repository: MailRepository, cipher: CredentialCipher) -> None:
        self.repository = repository
        self.cipher = cipher

    async def connect_gmail(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        profile: dict[str, object],
        tokens: GoogleTokens,
    ) -> MailAccount:
        provider_account_id = str(profile["emailAddress"]).casefold()
        account = await self.repository.account_by_provider_id(
            tenant_id,
            provider_account_id,
        )
        encrypted_refresh_token = (
            self.cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None
        )
        if account is None:
            if encrypted_refresh_token is None:
                raise ValueError("Google did not return a refresh token")
            account = MailAccount(
                tenant_id=tenant_id,
                connected_by_user_id=user_id,
                provider=MailProvider.GMAIL,
                provider_account_id=provider_account_id,
                email=provider_account_id,
                encrypted_refresh_token=encrypted_refresh_token,
                encrypted_access_token=self.cipher.encrypt(tokens.access_token),
                access_token_expires_at=tokens.expires_at,
                granted_scopes=tokens.scopes,
                status=AccountStatus.CONNECTED,
                history_cursor=None,
            )
            self.repository.add(account)
        else:
            if encrypted_refresh_token:
                account.encrypted_refresh_token = encrypted_refresh_token
            account.encrypted_access_token = self.cipher.encrypt(tokens.access_token)
            account.access_token_expires_at = tokens.expires_at
            account.granted_scopes = tokens.scopes
            account.status = AccountStatus.CONNECTED
            account.last_error = None
        await self.repository.commit()
        return account

    async def profile_for_tokens(self, tokens: GoogleTokens) -> dict[str, object]:
        return await GmailClient(tokens.access_token).profile()

    async def connect_microsoft(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        profile: dict[str, object],
        tokens: MicrosoftTokens,
    ) -> MailAccount:
        provider_account_id = str(profile["id"])
        email = str(profile.get("mail") or profile["userPrincipalName"]).casefold()
        account = await self.repository.account_by_provider_id(
            tenant_id,
            provider_account_id,
        )
        encrypted_refresh_token = (
            self.cipher.encrypt(tokens.refresh_token) if tokens.refresh_token else None
        )
        if account is None:
            if encrypted_refresh_token is None:
                raise ValueError("Microsoft did not return a refresh token")
            account = MailAccount(
                tenant_id=tenant_id,
                connected_by_user_id=user_id,
                provider=MailProvider.MICROSOFT,
                provider_account_id=provider_account_id,
                email=email,
                encrypted_refresh_token=encrypted_refresh_token,
                encrypted_access_token=self.cipher.encrypt(tokens.access_token),
                access_token_expires_at=tokens.expires_at,
                granted_scopes=tokens.scopes,
                status=AccountStatus.CONNECTED,
            )
            self.repository.add(account)
        else:
            if encrypted_refresh_token:
                account.encrypted_refresh_token = encrypted_refresh_token
            account.email = email
            account.encrypted_access_token = self.cipher.encrypt(tokens.access_token)
            account.access_token_expires_at = tokens.expires_at
            account.granted_scopes = tokens.scopes
            account.status = AccountStatus.CONNECTED
            account.last_error = None
        await self.repository.commit()
        return account

    async def microsoft_profile(
        self,
        tokens: MicrosoftTokens,
    ) -> dict[str, object]:
        return await MicrosoftGraphClient(tokens.access_token).profile()
