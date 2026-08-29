from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mail_control.modules.dashboard.cursor import decode_cursor, encode_cursor
from mail_control.modules.dashboard.schemas import AccountItem
from mail_control.modules.mail.models import AccountStatus, MailProvider


def test_cursor_round_trip() -> None:
    timestamp = datetime(2026, 7, 30, 12, 30, tzinfo=UTC)
    item_id = uuid4()

    cursor = encode_cursor(timestamp, item_id)

    assert decode_cursor(cursor) == (timestamp, item_id)


@pytest.mark.parametrize("cursor", ["invalid", "", "e30"])
def test_invalid_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(ValueError):
        decode_cursor(cursor)


def test_account_item_exposes_sync_diagnostic() -> None:
    item = AccountItem(
        id=uuid4(),
        provider=MailProvider.GMAIL,
        email="owner@example.com",
        status=AccountStatus.REAUTH_REQUIRED,
        last_synced_at=None,
        last_error="Google authorization expired; reconnect this Gmail account",
        message_count=0,
        alert_count=0,
    )

    assert item.last_error == "Google authorization expired; reconnect this Gmail account"
