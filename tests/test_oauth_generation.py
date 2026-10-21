from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mail_control.infrastructure.database.session import Database  # noqa: F401
from mail_control.modules.mail.auth_state import (
    AccountAuthorizationChanged,
    mark_reauth_if_current,
    update_account_if_current,
)
from mail_control.modules.mail.crypto import CredentialCipher
from mail_control.modules.mail.gmail import GmailReauthRequired, GoogleTokens
from mail_control.modules.mail.microsoft import MicrosoftTokens
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.service import MailAccountService
from mail_control.modules.mail.token_manager import AccountTokenManager


class AsyncAdapter:
    """Use actual SQLAlchemy SQL/dirty tracking against an isolated in-memory DB."""
    def __init__(self, session):
        self.session = session

    @property
    def no_autoflush(self):
        return self.session.no_autoflush

    async def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        return self.session.scalar(*args, **kwargs)

    async def refresh(self, *args, **kwargs):
        return self.session.refresh(*args, **kwargs)

    async def commit(self):
        self.session.commit()


@pytest.fixture
def data():
    engine = create_engine("sqlite://")
    MailAccount.__table__.create(engine)
    cipher = CredentialCipher("isolated-test-key")
    with Session(engine, expire_on_commit=False) as old, Session(
        engine, expire_on_commit=False,
    ) as new:
        account = MailAccount(
            id=uuid4(), tenant_id=uuid4(), connected_by_user_id=uuid4(),
            provider=MailProvider.GMAIL, provider_account_id="test@example.invalid",
            email="test@example.invalid", status=AccountStatus.CONNECTED,
            encrypted_refresh_token=cipher.encrypt("old-refresh"),
            encrypted_access_token=cipher.encrypt("old-access"),
            access_token_expires_at=datetime.now(UTC) - timedelta(minutes=5),
            granted_scopes=[],
        )
        old.add(account)
        old.commit()
        yield SimpleNamespace(
            old=old, new=new, session=AsyncAdapter(old), account=account, cipher=cipher,
        )
    engine.dispose()


async def reconnect(data, *, refresh="new-refresh", provider=MailProvider.GMAIL):
    service = MailAccountService(MailRepository(AsyncAdapter(data.new)), data.cipher)
    args = dict(
        tenant_id=data.account.tenant_id, user_id=data.account.connected_by_user_id,
    )
    token_values = dict(access_token="new-access", refresh_token=refresh,
                        expires_at=datetime.now(UTC) + timedelta(hours=1), scopes=[])
    if provider == MailProvider.GMAIL:
        return await service.connect_gmail(
            **args, profile={"emailAddress": data.account.provider_account_id},
            tokens=GoogleTokens(**token_values),
        )
    return await service.connect_microsoft(
        **args, profile={"id": data.account.provider_account_id, "mail": data.account.email},
        tokens=MicrosoftTokens(**token_values),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [MailProvider.GMAIL, MailProvider.MICROSOFT])
async def test_reauthorization_changes_generation_even_without_rotating_provider_token(
    data, provider,
):
    data.account.provider = provider
    data.old.commit()
    old_grant = data.account.encrypted_refresh_token
    new_account = await reconnect(data, refresh=None, provider=provider)
    assert new_account.encrypted_refresh_token != old_grant
    assert data.cipher.decrypt(new_account.encrypted_refresh_token) == "old-refresh"


@pytest.mark.asyncio
async def test_stale_invalid_grant_cannot_undo_new_authorization_even_with_dirty_orm(data):
    old_grant = data.account.encrypted_refresh_token
    await reconnect(data)
    error = GmailReauthRequired("invalid_grant")
    error._mail_expected_grant = old_grant
    data.account.status = AccountStatus.REAUTH_REQUIRED
    data.account.encrypted_access_token = None
    assert not await mark_reauth_if_current(data.session, data.account, error)
    await data.session.commit()
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.CONNECTED
    assert data.cipher.decrypt(data.account.encrypted_access_token) == "new-access"
    assert data.cipher.decrypt(data.account.encrypted_refresh_token) == "new-refresh"


@pytest.mark.asyncio
async def test_current_invalid_grant_still_clears_access_and_requests_authorization(data):
    assert await mark_reauth_if_current(data.session, data.account, GmailReauthRequired("revoked"))
    await data.session.commit()
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.REAUTH_REQUIRED
    assert data.account.encrypted_access_token is None


@pytest.mark.asyncio
async def test_current_status_update_cannot_revive_disconnected_account(data):
    new = data.new.get(MailAccount, data.account.id)
    new.status = AccountStatus.DISCONNECTED
    data.new.commit()
    assert not await update_account_if_current(
        data.session, data.account, data.account.encrypted_refresh_token,
        {"status": AccountStatus.CONNECTED},
    )
    assert data.account.status == AccountStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_old_successful_sync_cannot_replace_new_grant_state_or_cursor(data):
    old_grant = data.account.encrypted_refresh_token
    await reconnect(data)
    data.account.history_cursor = "obsolete-result"
    assert not await update_account_if_current(
        data.session, data.account, old_grant,
        {"status": AccountStatus.CONNECTED, "history_cursor": "obsolete-result"},
    )
    await data.session.commit()
    assert data.account.history_cursor is None
    assert data.cipher.decrypt(data.account.encrypted_access_token) == "new-access"


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_refresh_response_from_old_generation_cannot_replace_new_consent(
    data, fails, monkeypatch,
):
    lock = SimpleNamespace(acquire=AsyncMock(return_value=True), release=AsyncMock())
    resources = SimpleNamespace(redis=SimpleNamespace(lock=lambda *a, **k: lock))
    settings = SimpleNamespace(
        credential_encryption_key="isolated-test-key", app_secret_key="unused",
    )
    manager = AccountTokenManager(data.account, data.session, resources, settings)
    old_grant = data.account.encrypted_refresh_token
    # SQLite discards timezone offsets; force the same aware value a PostgreSQL
    # timestamptz returns, without replacing SQL execution or dirty tracking.
    real_refresh = data.session.refresh

    async def aware_refresh(account, **kwargs):
        await real_refresh(account, **kwargs)
        if account.access_token_expires_at and account.access_token_expires_at.tzinfo is None:
            from sqlalchemy.orm.attributes import set_committed_value
            set_committed_value(account, "access_token_expires_at",
                                account.access_token_expires_at.replace(tzinfo=UTC))

    data.session.refresh = aware_refresh

    async def old_provider_reply(refresh_token):
        assert refresh_token == "old-refresh"
        await reconnect(data)
        if fails:
            raise GmailReauthRequired("invalid_grant")
        return GoogleTokens("obsolete-access", "obsolete-refresh",
                            datetime.now(UTC) + timedelta(hours=1), [])

    monkeypatch.setattr(manager, "_refresh", old_provider_reply)
    expected_error = GmailReauthRequired if fails else AccountAuthorizationChanged
    with pytest.raises(expected_error) as caught:
        await manager.access_token()
    if fails:
        assert caught.value._mail_expected_grant == old_grant
        assert not await mark_reauth_if_current(data.session, data.account, caught.value)
    await data.session.commit()
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.CONNECTED
    assert data.cipher.decrypt(data.account.encrypted_access_token) == "new-access"
    assert data.cipher.decrypt(data.account.encrypted_refresh_token) == "new-refresh"
    lock.release.assert_awaited_once()


@pytest.mark.asyncio
async def test_stale_grant_cannot_update_a_different_tenant(data):
    actual_tenant = data.account.tenant_id
    from sqlalchemy.orm.attributes import set_committed_value
    set_committed_value(data.account, "tenant_id", uuid4())
    assert not await update_account_if_current(
        data.session, data.account, data.account.encrypted_refresh_token,
        {"status": AccountStatus.REAUTH_REQUIRED},
    )
    set_committed_value(data.account, "tenant_id", actual_tenant)
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.CONNECTED


@pytest.mark.asyncio
async def test_live_generation_can_save_rotated_tokens_without_dirty_status_leaking(data):
    grant = data.account.encrypted_refresh_token
    data.account.status = AccountStatus.REAUTH_REQUIRED
    rotated = data.cipher.encrypt("rotated-refresh")
    assert await update_account_if_current(data.session, data.account, grant, {
        "encrypted_refresh_token": rotated,
        "encrypted_access_token": data.cipher.encrypt("rotated-access"),
    })
    await data.session.commit()
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.CONNECTED
    assert data.account.encrypted_refresh_token == rotated


@pytest.mark.asyncio
async def test_pausing_or_reauthorizing_after_old_read_is_detected_by_sql_not_memory(data):
    old_grant = data.account.encrypted_refresh_token
    await reconnect(data)
    # No in-memory refresh on the old session: the atomic WHERE must decide.
    assert data.account.encrypted_refresh_token == old_grant
    assert not await update_account_if_current(data.session, data.account, old_grant, {
        "encrypted_refresh_token": data.cipher.encrypt("old-result"),
        "status": AccountStatus.ERROR, "last_error": "obsolete failure",
    })
    await data.session.commit()
    data.old.refresh(data.account)
    assert data.account.status == AccountStatus.CONNECTED
    assert data.account.last_error is None
