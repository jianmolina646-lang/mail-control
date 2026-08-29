from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from mail_control.modules.mail.gmail import (
    GMAIL_SCOPE,
    GmailError,
    GmailOAuth,
    GmailReauthRequired,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, seconds: int, value: str) -> None:
        assert seconds == 600
        self.values[key] = value

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


def test_reauth_error_is_a_gmail_error() -> None:
    assert issubclass(GmailReauthRequired, GmailError)


@pytest.mark.asyncio
async def test_oauth_url_uses_offline_consent_pkce_and_one_time_state() -> None:
    redis = FakeRedis()
    oauth = GmailOAuth(
        redis,  # type: ignore[arg-type]
        client_id="google-client",
        client_secret="google-secret",
        redirect_uri="https://example.com/callback",
    )
    tenant_id = uuid4()
    user_id = uuid4()

    url = await oauth.authorization_url(tenant_id, user_id)

    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "code_challenge_method=S256" in url
    assert GMAIL_SCOPE.replace(":", "%3A").replace("/", "%2F") in url

    state = next(iter(redis.values)).removeprefix("oauth:gmail:")
    payload = await oauth.consume_state(state)
    assert payload.tenant_id == tenant_id
    assert payload.user_id == user_id
    with pytest.raises(GmailError):
        await oauth.consume_state(state)


def gmail_message() -> dict[str, Any]:
    return {
        "id": "gmail-123",
        "threadId": "thread-1",
        "historyId": "456",
        "internalDate": "1722333600000",
        "sizeEstimate": 1234,
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "Payment received",
        "payload": {
            "headers": [
                {"name": "From", "value": "Netflix <info@netflix.com>"},
                {"name": "To", "value": "owner@example.com"},
                {"name": "Subject", "value": "Your payment"},
                {"name": "Message-ID", "value": "<id@example.com>"},
                {"name": "Date", "value": "Tue, 30 Jul 2026 10:00:00 +0000"},
            ]
        },
    }
