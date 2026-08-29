from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.worker import REAUTH_REQUIRED_MESSAGE, mark_reauth_required


def test_mark_reauth_required_clears_stale_access_token() -> None:
    account = MailAccount(
        id=uuid4(),
        tenant_id=uuid4(),
        connected_by_user_id=uuid4(),
        provider=MailProvider.GMAIL,
        provider_account_id="owner@example.com",
        email="owner@example.com",
        encrypted_refresh_token="encrypted-refresh",
        encrypted_access_token="encrypted-access",
        access_token_expires_at=datetime.now(UTC),
        status=AccountStatus.CONNECTED,
    )

    mark_reauth_required(account)

    assert account.status is AccountStatus.REAUTH_REQUIRED
    assert account.last_error == REAUTH_REQUIRED_MESSAGE
    assert account.encrypted_access_token is None
    assert account.access_token_expires_at is None
