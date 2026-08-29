from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from mail_control.modules.mail.microsoft import (
    MICROSOFT_AUTH_URL,
    OAUTH_STATE_TTL_SECONDS,
    MicrosoftError,
    MicrosoftOAuth,
)
from mail_control.modules.mail.microsoft_sync import microsoft_message_values
from mail_control.modules.mail.models import MailAccount, MailProvider


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, seconds: int, value: str) -> None:
        assert seconds == OAUTH_STATE_TTL_SECONDS
        self.values[key] = value

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


@pytest.mark.asyncio
async def test_microsoft_oauth_supports_personal_accounts_offline_and_pkce() -> None:
    redis = FakeRedis()
    oauth = MicrosoftOAuth(
        redis,  # type: ignore[arg-type]
        client_id="microsoft-client",
        client_secret="microsoft-secret",
        redirect_uri="https://example.com/microsoft/callback",
    )
    tenant_id = uuid4()
    user_id = uuid4()

    url = await oauth.authorization_url(tenant_id, user_id)

    assert url.startswith(MICROSOFT_AUTH_URL)
    assert "offline_access" in url
    assert "Mail.Read" in url
    assert "code_challenge_method=S256" in url

    state = next(iter(redis.values)).removeprefix("oauth:microsoft:")
    stored = await oauth.consume_state(state)
    assert stored.tenant_id == tenant_id
    assert stored.user_id == user_id
    with pytest.raises(MicrosoftError):
        await oauth.consume_state(state)


def graph_message() -> dict[str, Any]:
    return {
        "id": "immutable-message-id",
        "conversationId": "conversation-1",
        "internetMessageId": "<message@example.com>",
        "subject": "Microsoft payment",
        "from": {"emailAddress": {"address": "billing@microsoft.com"}},
        "toRecipients": [{"emailAddress": {"address": "owner@outlook.com"}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2026-07-30T12:00:00Z",
        "bodyPreview": "Your payment was received",
        "parentFolderId": "inbox-id",
        "isRead": False,
    }


def test_graph_message_mapping_preserves_payload() -> None:
    account = MailAccount(
        id=uuid4(),
        tenant_id=uuid4(),
        connected_by_user_id=uuid4(),
        provider=MailProvider.MICROSOFT,
        provider_account_id="graph-user-id",
        email="owner@outlook.com",
        encrypted_refresh_token="encrypted",
    )

    values = microsoft_message_values(account, graph_message())

    assert values["provider_message_id"] == "immutable-message-id"
    assert values["sender"] == "billing@microsoft.com"
    assert values["recipients"] == ["owner@outlook.com"]
    assert values["payload"] == graph_message()
