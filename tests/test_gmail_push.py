from __future__ import annotations

import base64
import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from mail_control.modules.mail.gmail import GmailClient
from mail_control.modules.mail.gmail_push import decode_pubsub_payload, enqueue_from_push
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.settings import Settings


class FakeRedis:
    def __init__(self) -> None:
        self.values: set[str] = set()

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool = False,
    ) -> bool:
        assert value == "1"
        assert ex == 120
        if nx and key in self.values:
            return False
        self.values.add(key)
        return True


class FakeExchange:
    def __init__(self) -> None:
        self.published: list[tuple[bytes, str]] = []

    async def publish(self, message: Any, *, routing_key: str) -> None:
        self.published.append((message.body, routing_key))


class FakeChannel:
    def __init__(self) -> None:
        self.default_exchange = FakeExchange()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeRabbit:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()

    async def channel(self) -> FakeChannel:
        return self.channel_instance


class FakeResources:
    def __init__(self) -> None:
        self.redis = FakeRedis()
        self.rabbitmq = FakeRabbit()


class FakeSession:
    def __init__(self, account: MailAccount) -> None:
        self.account = account

    async def scalar(self, statement: Any) -> MailAccount:
        return self.account


def settings() -> Settings:
    return Settings(
        app_secret_key="x" * 32,
        database_url="postgresql+asyncpg://example",
        redis_url="redis://example",
        rabbitmq_url="amqp://example",
    )


@pytest.mark.asyncio
async def test_gmail_watch_request_uses_topic_and_inbox_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"historyId": "123", "expiration": "1780000000000"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    result = await GmailClient("token").watch(
        topic_name="projects/example/topics/mail-control-gmail-push",
        label_ids=("INBOX",),
    )

    assert result["historyId"] == "123"
    assert seen["url"].endswith("/gmail/v1/users/me/watch")
    assert seen["json"] == {
        "topicName": "projects/example/topics/mail-control-gmail-push",
        "labelFilterBehavior": "INCLUDE",
        "labelIds": ["INBOX"],
    }


def test_decode_pubsub_payload_reads_email_and_history_id() -> None:
    payload = {"emailAddress": "User@Example.com", "historyId": "987"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    decoded = decode_pubsub_payload({"message": {"data": encoded}})

    assert decoded == {"emailAddress": "user@example.com", "historyId": "987"}


@pytest.mark.asyncio
async def test_push_event_is_deduplicated_before_enqueue() -> None:
    tenant_id = uuid4()
    account_id = uuid4()
    account = MailAccount(
        id=account_id,
        tenant_id=tenant_id,
        connected_by_user_id=uuid4(),
        provider=MailProvider.GMAIL,
        provider_account_id="user@example.com",
        email="user@example.com",
        encrypted_refresh_token="refresh",
        granted_scopes=[],
        status=AccountStatus.CONNECTED,
    )
    resources = FakeResources()
    session = FakeSession(account)

    first = await enqueue_from_push(
        session,  # type: ignore[arg-type]
        resources,  # type: ignore[arg-type]
        settings(),
        email="user@example.com",
        history_id="123",
    )
    second = await enqueue_from_push(
        session,  # type: ignore[arg-type]
        resources,  # type: ignore[arg-type]
        settings(),
        email="user@example.com",
        history_id="123",
    )

    published = resources.rabbitmq.channel_instance.default_exchange.published
    assert first is True
    assert second is False
    assert len(published) == 1
    assert published[0][1] == "mail.sync.gmail"
