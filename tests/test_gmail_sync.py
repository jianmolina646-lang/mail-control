from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from structlog.testing import capture_logs

from mail_control.modules.mail.gmail import GmailClient, GmailMessageNotFound, GmailTransientError
from mail_control.modules.mail.models import (
    AccountStatus,
    MailAccount,
    MailProvider,
    MailSyncCursor,
)
from mail_control.modules.mail.sync import GmailSyncService, message_values
from tests.test_gmail import gmail_message


class MissingMessageClient:
    async def history(self, start_history_id: str, *, page_token=None) -> dict[str, Any]:
        return {"historyId": start_history_id}

    async def profile(self) -> dict[str, Any]:
        return {"historyId": "initial-history"}

    async def list_messages(self, *, page_token: str | None = None) -> dict[str, Any]:
        return {"messages": [{"id": "deleted-message"}]}

    async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
        raise GmailMessageNotFound


class FakeRepository:
    def __init__(self) -> None:
        self.commits = 0
        self.checkpoints: list[object] = []
        self.initial_cursor: MailSyncCursor | None = None

    def add(self, value: object) -> None:
        if isinstance(value, MailSyncCursor):
            self.initial_cursor = value

    async def cursor(self, tenant_id, account_id, resource_key):
        return self.initial_cursor

    async def delete_cursor(self, cursor):
        self.initial_cursor = None

    async def active_provider_message_ids(self, account_id):
        return set()

    async def mark_deleted(self, account_id, message_id, deleted_at):
        return None

    async def update_account_state(self, account, values, error=None):
        for name, value in values.items():
            setattr(account, name, value)
        return True

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def checkpoint(self, tenant_id: object) -> None:
        self.checkpoints.append(tenant_id)
        await self.commit()

    async def existing_provider_message_ids(
        self, account_id: object, provider_message_ids: list[str],
    ) -> set[str]:
        return set()

    async def upsert_message(self, values: dict[str, object]) -> bool:
        raise AssertionError("a deleted Gmail message must not be stored")

    async def queue_analysis(
        self,
        account_id: object,
        message_id: str,
        tenant_id: object,
    ) -> None:
        raise AssertionError("a deleted Gmail message must not be analyzed")


class RecordingRepository(FakeRepository):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict[str, object]] = []
        self.deleted: list[str] = []

    async def active_provider_message_ids(self, account_id):
        return {
            str(item["provider_message_id"]) for item in self.messages
            if item["mail_account_id"] == account_id
            and item["provider_message_id"] not in self.deleted
        }

    async def existing_provider_message_ids(
        self, account_id: object, provider_message_ids: list[str],
    ) -> set[str]:
        return {
            str(item["provider_message_id"]) for item in self.messages
            if item["mail_account_id"] == account_id
            and item["provider_message_id"] in provider_message_ids
        }

    async def upsert_message(self, values: dict[str, object]) -> bool:
        for index, item in enumerate(self.messages):
            if item["provider_message_id"] == values["provider_message_id"]:
                self.messages[index] = values
                return False
        self.messages.append(values)
        return True

    async def queue_analysis(
        self,
        account_id: object,
        message_id: str,
        tenant_id: object,
    ) -> None:
        return None

    async def mark_deleted(
        self,
        account_id: object,
        message_id: str,
        deleted_at: object,
    ) -> None:
        self.deleted.append(message_id)


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
    assert repository.commits == 2
    assert repository.checkpoints == [mail_account.tenant_id]
    assert logs == [
        {
            "account_id": str(mail_account.id),
            "event": "gmail_message_missing_during_sync",
            "log_level": "info",
            "sync_kind": "initial",
        }
    ]


@pytest.mark.asyncio
async def test_empty_full_sync_still_saves_a_replayable_history_checkpoint() -> None:
    class EmptyMailbox:
        async def history(self, start_history_id, *, page_token=None):
            return {"historyId": start_history_id}

        async def profile(self) -> dict[str, Any]:
            return {"historyId": "baseline"}

        async def list_messages(self, *, page_token: str | None = None) -> dict[str, Any]:
            return {"messages": []}

    repository = RecordingRepository()
    mail_account = account()

    await GmailSyncService(repository).synchronize(  # type: ignore[arg-type]
        mail_account, EmptyMailbox()  # type: ignore[arg-type]
    )

    assert mail_account.history_cursor == "baseline"


@pytest.mark.asyncio
async def test_interrupted_full_import_retries_without_redownloading_saved_messages() -> None:
    class InterruptedMailbox:
        interrupted = True

        async def history(self, start_history_id, *, page_token=None):
            return {"historyId": start_history_id}

        def __init__(self) -> None:
            self.downloaded: list[str] = []

        async def profile(self) -> dict[str, Any]:
            return {"historyId": "baseline"}

        async def list_messages(self, *, page_token: str | None = None) -> dict[str, Any]:
            if page_token is None:
                return {"messages": [{"id": "first"}], "nextPageToken": "second-page"}
            if self.interrupted:
                raise GmailTransientError("temporary test interruption")
            return {"messages": [{"id": "second"}]}

        async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
            self.downloaded.append(message_id)
            message = gmail_message()
            message["id"] = message_id
            return message

    repository = RecordingRepository()
    mail_account = account()
    client = InterruptedMailbox()
    service = GmailSyncService(repository)  # type: ignore[arg-type]

    with pytest.raises(GmailTransientError):
        await service.synchronize(mail_account, client)  # type: ignore[arg-type]

    assert mail_account.status == AccountStatus.ERROR
    assert mail_account.history_cursor is None
    assert mail_account.last_synced_at is None
    assert client.downloaded == ["first"]
    assert repository.checkpoints == [mail_account.tenant_id]

    client.interrupted = False
    run = await service.synchronize(mail_account, client)  # type: ignore[arg-type]

    assert run.status.value == "succeeded"
    assert mail_account.status == AccountStatus.CONNECTED
    assert mail_account.last_error is None
    assert mail_account.history_cursor == "baseline"
    assert mail_account.last_synced_at is not None
    assert client.downloaded == ["first", "second"]
    assert [item["provider_message_id"] for item in repository.messages] == ["first", "second"]


@pytest.mark.asyncio
async def test_incremental_cursor_is_not_advanced_when_a_later_history_page_fails() -> None:
    class LaterPageFails:
        async def history(
            self, start_history_id: str, *, page_token: str | None = None
        ) -> dict[str, Any]:
            assert start_history_id == "checkpoint"
            if page_token is None:
                return {
                    "history": [{"labelsAdded": [{"message": {"id": "first"}}]}],
                    "nextPageToken": "second-page",
                }
            raise RuntimeError("simulated later page failure")

        async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
            message = gmail_message()
            message["id"] = message_id
            return message

    repository = RecordingRepository()
    mail_account = account()
    mail_account.history_cursor = "checkpoint"

    with pytest.raises(RuntimeError, match="later page"):
        await GmailSyncService(repository).synchronize(  # type: ignore[arg-type]
            mail_account, LaterPageFails()  # type: ignore[arg-type]
        )

    assert mail_account.history_cursor == "checkpoint"
    assert [item["provider_message_id"] for item in repository.messages] == ["first"]
