import json

import pytest

from mail_control.modules.mail.gmail import (
    GmailHistoryExpired,
    GmailMessageNotFound,
    GmailTransientError,
)
from mail_control.modules.mail.models import AccountStatus
from mail_control.modules.mail.sync import GmailSyncService
from tests.test_gmail import gmail_message
from tests.test_gmail_sync import RecordingRepository, account


class ChangingMailbox:
    def __init__(self):
        self.baseline = "100"
        self.interrupt = True
        self.unread = True
        self.deleted = False
        self.expired = set()
        self.replay_fails = False
        self.downloaded = []
        self.replayed = []

    async def profile(self):
        return {"historyId": self.baseline}

    async def list_messages(self, *, page_token=None):
        if page_token is None:
            return {"messages": [] if self.deleted else [{"id": "A"}], "nextPageToken": "p2"}
        if self.interrupt:
            raise GmailTransientError("simulated interruption")
        return {"messages": [{"id": "B"}]}

    async def get_message(self, message_id, *, full=True):
        self.downloaded.append(message_id)
        if message_id == "A" and self.deleted:
            raise GmailMessageNotFound()
        message = gmail_message()
        message["id"] = message_id
        message["labelIds"] = ["INBOX", "UNREAD"] if self.unread else ["INBOX"]
        return message

    async def history(self, cursor, *, page_token=None):
        self.replayed.append(cursor)
        if cursor in self.expired:
            raise GmailHistoryExpired()
        if self.replay_fails:
            raise GmailTransientError("replay unavailable")
        return {"historyId": self.baseline, "history": [{
            "labelsRemoved": [{"message": {"id": "A"}}],
        }]} if cursor != self.baseline else {"historyId": self.baseline}


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted", [False, True])
async def test_initial_retry_replays_changes_since_original_not_new_baseline(deleted):
    repository, mail_account, client = RecordingRepository(), account(), ChangingMailbox()
    service = GmailSyncService(repository)
    with pytest.raises(GmailTransientError):
        await service.synchronize(mail_account, client)
    assert json.loads(repository.initial_cursor.cursor)["history_id"] == "100"
    assert mail_account.history_cursor is None
    client.baseline, client.unread, client.interrupt, client.deleted = "200", False, False, deleted
    await service.synchronize(mail_account, client)
    assert client.replayed == ["100"]
    if deleted:
        assert "A" in repository.deleted
    else:
        assert next(m for m in repository.messages if m["provider_message_id"] == "A")["is_read"]
    assert mail_account.history_cursor == "200"
    assert repository.initial_cursor is None
    assert mail_account.status == AccountStatus.CONNECTED


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted", [False, True])
async def test_expired_history_refreshes_existing_messages_and_verifies_missing_ids(deleted):
    repository, mail_account, client = RecordingRepository(), account(), ChangingMailbox()
    service = GmailSyncService(repository)
    with pytest.raises(GmailTransientError):
        await service.synchronize(mail_account, client)
    repository.initial_cursor = None
    mail_account.history_cursor = "expired"
    client.expired = {"expired"}
    client.baseline, client.unread, client.interrupt, client.deleted = "200", False, False, deleted
    await service.synchronize(mail_account, client)
    assert client.downloaded.count("A") == 2
    if deleted:
        assert "A" in repository.deleted
    else:
        assert next(m for m in repository.messages if m["provider_message_id"] == "A")["is_read"]
    assert mail_account.history_cursor == "200"


@pytest.mark.asyncio
async def test_expired_initial_baseline_is_rebuilt_and_replay_failure_does_not_advance_cursor():
    repository, mail_account, client = RecordingRepository(), account(), ChangingMailbox()
    service = GmailSyncService(repository)
    with pytest.raises(GmailTransientError):
        await service.synchronize(mail_account, client)
    client.expired = {"100"}
    client.baseline, client.unread, client.interrupt = "200", False, False
    await service.synchronize(mail_account, client)
    assert client.replayed == ["100", "200"]
    assert next(m for m in repository.messages if m["provider_message_id"] == "A")["is_read"]
    assert mail_account.history_cursor == "200"

    mail_account.history_cursor = None
    client.replay_fails = True
    with pytest.raises(GmailTransientError):
        await service.synchronize(mail_account, client)
    assert mail_account.history_cursor is None
    assert repository.initial_cursor is not None
    assert mail_account.status == AccountStatus.ERROR
