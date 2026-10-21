import os

import pytest
from sqlalchemy import update

from mail_control.modules.mail.auth_state import mark_reauth_if_current, update_account_if_current
from mail_control.modules.mail.gmail import GmailReauthRequired, GmailTransientError
from mail_control.modules.mail.models import AccountStatus, MailAccount
from mail_control.modules.mail.repository import MailRepository
from mail_control.modules.mail.sync import GmailSyncService
from tests.test_gmail_baseline import ChangingMailbox
from tests.test_mail_postgres import dataset  # noqa: F401

pytestmark = pytest.mark.skipif(
    not os.environ.get("MAIL_TEST_DATABASE_URL"), reason="requires isolated PostgreSQL",
)


async def test_pg_stale_authorization_is_not_written_before_conditional_update(dataset):  # noqa: F811
    account = dataset.accounts[0]
    old_grant = account.encrypted_refresh_token
    await dataset.session.execute(update(MailAccount.__table__).where(
        MailAccount.id == account.id,
    ).values(encrypted_refresh_token="new-generation", encrypted_access_token="new-access"))
    account.status = AccountStatus.REAUTH_REQUIRED
    account.encrypted_access_token = None
    error = GmailReauthRequired("old provider response")
    error._mail_expected_grant = old_grant
    assert not await mark_reauth_if_current(dataset.session, account, error)
    await dataset.session.flush()
    await dataset.session.refresh(account)
    assert account.status == AccountStatus.CONNECTED
    assert account.encrypted_access_token == "new-access"
    assert account.encrypted_refresh_token == "new-generation"
    assert await mark_reauth_if_current(dataset.session, account, GmailReauthRequired("current"))
    await dataset.session.flush()
    await dataset.session.refresh(account)
    assert account.status == AccountStatus.REAUTH_REQUIRED
    assert account.encrypted_access_token is None


async def test_pg_generation_guard_blocks_old_sync_completion(dataset):  # noqa: F811
    account = dataset.accounts[0]
    old_grant = account.encrypted_refresh_token
    await dataset.session.execute(update(MailAccount.__table__).where(
        MailAccount.id == account.id,
    ).values(encrypted_refresh_token="new-generation", history_cursor="new-cursor"))
    account.history_cursor = "old-cursor"
    assert not await update_account_if_current(dataset.session, account, old_grant, {
        "status": AccountStatus.CONNECTED, "history_cursor": "old-cursor",
    })
    await dataset.session.flush()
    await dataset.session.refresh(account)
    assert account.history_cursor == "new-cursor"


async def test_pg_initial_baseline_persists_across_page_commit_and_retry(dataset):  # noqa: F811
    account = dataset.accounts[0]
    repository = MailRepository(dataset.session)
    client = ChangingMailbox()
    service = GmailSyncService(repository)
    with pytest.raises(GmailTransientError):
        await service.synchronize(account, client)
    from mail_control.infrastructure.database.tenant import set_tenant_context
    await set_tenant_context(dataset.session, account.tenant_id)
    checkpoint = await repository.cursor(account.tenant_id, account.id, "gmail:initial")
    assert checkpoint is not None and '"100"' in checkpoint.cursor
    assert account.history_cursor is None
    client.interrupt, client.unread, client.baseline = False, False, "200"
    await service.synchronize(account, client)
    await set_tenant_context(dataset.session, account.tenant_id)
    await dataset.session.refresh(account)
    assert account.status == AccountStatus.CONNECTED
    assert account.history_cursor == "200"
    assert await repository.cursor(account.tenant_id, account.id, "gmail:initial") is None
