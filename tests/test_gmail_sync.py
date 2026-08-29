from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from structlog.testing import capture_logs

from mail_control.modules.mail.gmail import GmailClient, GmailMessageNotFound
from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.mail.sync import GmailSyncService, message_values
from tests.test_gmail import gmail_message


class MissingMessageClient:
    async def list_messages(self, *, page_token: str | None = None) -> dict[str, Any]:
        return {"messages": [{"id": "deleted-message"}]}

    async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
        raise GmailMessageNotFound


class FakeRepository:
    def __init__(self) -> None:
        self.commits = 0

    def add(self, value: object) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def upsert_message(self, values: dict[str, object]) -> bool:
        raise AssertionError("a deleted Gmail message must not be stored")

    async def queue_analysis(
        self,
        account_id: object,
        message_id: str,
        tenant_id: object,
    ) -> None:
        raise AssertionError("a deleted Gmail message must not be analyzed")


def account() -> MailAccount:
    return MailAccount(
        id=uuid4(),
        tenant_id=uuid4(),
        connected_by_user_id=uuid4(),
        provider=MailProvider.GMAIL,
        provider_account_id="user@example.com",
        email="user@example.com",
        encrypted_refresh_token="refresh",
        granted_scopes=[],
        status=AccountStatus.CONNECTED,
    )


def test_message_mapping_preserves_real_gmail_payload() -> None:
    mail_account = MailAccount(
        id=uuid4(),
        tenant_id=uuid4(),
        connected_by_user_id=uuid4(),
        provider=MailProvider.GMAIL,
        provider_account_id="owner@example.com",
        email="owner@example.com",
        encrypted_refresh_token="encrypted",
    )

    values = message_values(mail_account, gmail_message())

    assert values["provider_message_id"] == "gmail-123"
    assert values["sender"] == "Netflix <info@netflix.com>"
    assert values["subject"] == "Your payment"
    assert values["label_ids"] == ["INBOX", "UNREAD"]
    assert values["payload"] == gmail_message()


@pytest.mark.asyncio
async def test_get_message_converts_404_to_message_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"}, request=request)

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(GmailMessageNotFound):
        await GmailClient("token").get_message("deleted-message")


@pytest.mark.asyncio
async def test_full_sync_skips_message_deleted_after_listing() -> None:
    repository = FakeRepository()
    mail_account = account()

    with capture_logs() as logs:
        run = await GmailSyncService(repository).synchronize(  # type: ignore[arg-type]
            mail_account,
            MissingMessageClient(),  # type: ignore[arg-type]
        )

    assert run.status.value == "succeeded"
    assert mail_account.status is AccountStatus.CONNECTED
    assert mail_account.last_error is None
    assert repository.commits == 1
    assert logs == [
        {
            "account_id": str(mail_account.id),
            "event": "gmail_message_missing_during_sync",
            "log_level": "info",
            "sync_kind": "initial",
        }
    ]
