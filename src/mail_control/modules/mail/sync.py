from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import structlog

from mail_control.modules.mail.gmail import (
    GmailClient,
    GmailHistoryExpired,
    GmailMessageNotFound,
    GmailReauthRequired,
)
from mail_control.modules.mail.models import (
    AccountStatus,
    MailAccount,
    MailProvider,
    SyncKind,
    SyncRun,
    SyncStatus,
)
from mail_control.modules.mail.repository import MailRepository

logger = structlog.get_logger(__name__)


def message_values(account: MailAccount, message: dict[str, Any]) -> dict[str, object]:
    headers = {
        item["name"].casefold(): item.get("value", "")
        for item in message.get("payload", {}).get("headers", [])
    }
    received_at = None
    if headers.get("date"):
        try:
            received_at = parsedate_to_datetime(headers["date"])
        except (TypeError, ValueError):
            received_at = None
    internal_date = message.get("internalDate")
    labels = message.get("labelIds", [])
    mailbox = next((box for label, box in (
        ("TRASH", "trash"), ("SPAM", "spam"), ("DRAFT", "drafts"),
        ("INBOX", "inbox"), ("SENT", "sent"),
    ) if label in labels), "archive")
    is_read = "UNREAD" not in labels
    is_starred = "STARRED" in labels
    return {
        "tenant_id": account.tenant_id,
        "mail_account_id": account.id,
        "provider_message_id": message["id"],
        "thread_id": message.get("threadId"),
        "history_id": message.get("historyId"),
        "internet_message_id": headers.get("message-id"),
        "sender": headers.get("from"),
        "recipients": [headers[name] for name in ("to", "cc", "bcc") if headers.get(name)],
        "subject": headers.get("subject"),
        "snippet": message.get("snippet"),
        "received_at": received_at,
        "internal_date_ms": int(internal_date) if internal_date else None,
        "size_estimate": message.get("sizeEstimate"),
        "label_ids": message.get("labelIds", []),
        "payload": message,
        "deleted_at": None,
        "is_read": is_read,
        "is_starred": is_starred,
        "mailbox": mailbox,
        "provider_is_read": is_read,
        "provider_is_starred": is_starred,
        "provider_mailbox": mailbox,
        "provider_folder_id": None,
    }


class GmailSyncService:
    def __init__(self, repository: MailRepository) -> None:
        self.repository = repository

    async def synchronize(self, account: MailAccount, client: GmailClient) -> SyncRun:
        if account.provider is not MailProvider.GMAIL:
            raise ValueError("Gmail synchronization requires a Gmail account")
        kind = SyncKind.INCREMENTAL if account.history_cursor else SyncKind.INITIAL
        run = SyncRun(
            tenant_id=account.tenant_id,
            mail_account_id=account.id,
            kind=kind,
            status=SyncStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.repository.add(run)
        run.messages_seen = run.messages_created = run.messages_updated = 0
        account.status = AccountStatus.SYNCING
        await self.repository.flush()
        try:
            if kind is SyncKind.INITIAL:
                await self._full_sync(account, client, run)
            else:
                try:
                    await self._incremental_sync(account, client, run)
                except GmailHistoryExpired:
                    run.kind = SyncKind.INITIAL
                    await self._full_sync(account, client, run)
            run.status = SyncStatus.SUCCEEDED
            account.status = AccountStatus.CONNECTED
            account.last_error = None
            account.last_synced_at = datetime.now(UTC)
        except Exception as error:
            run.status = SyncStatus.FAILED
            run.error = str(error)[:2000]
            account.status = (
                AccountStatus.REAUTH_REQUIRED if isinstance(error, GmailReauthRequired)
                else AccountStatus.ERROR
            )
            account.last_error = run.error
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            await self.repository.commit()
        return run

    async def _full_sync(
        self,
        account: MailAccount,
        client: GmailClient,
        run: SyncRun,
    ) -> None:
        page_token: str | None = None
        # Capture the baseline before listing: messages can arrive during an import,
        # and even an empty mailbox needs a usable history checkpoint.
        baseline = (await client.profile()).get("historyId")
        while True:
            page = await client.list_messages(page_token=page_token)
            for item in page.get("messages", []):
                try:
                    message = await client.get_message(item["id"], full=True)
                except GmailMessageNotFound:
                    logger.info(
                        "gmail_message_missing_during_sync",
                        account_id=str(account.id),
                        sync_kind=run.kind.value,
                    )
                    continue
                await self._store(account, message, run)
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        if baseline:
            account.history_cursor = str(baseline)

    async def _incremental_sync(
        self,
        account: MailAccount,
        client: GmailClient,
        run: SyncRun,
    ) -> None:
        assert account.history_cursor is not None
        page_token: str | None = None
        cursor = account.history_cursor
        while True:
            page = await client.history(cursor, page_token=page_token)
            message_ids = {
                change["message"]["id"]
                for history in page.get("history", [])
                for event in ("messagesAdded", "messagesDeleted", "labelsAdded", "labelsRemoved")
                for change in history.get(event, [])
            }
            for message_id in message_ids:
                try:
                    message = await client.get_message(message_id, full=True)
                except GmailMessageNotFound:
                    await self.repository.mark_deleted(account.id, message_id, datetime.now(UTC))
                    logger.info(
                        "gmail_message_missing_during_sync",
                        account_id=str(account.id),
                        sync_kind=run.kind.value,
                    )
                    continue
                await self._store(
                    account,
                    message,
                    run,
                )
            page_token = page.get("nextPageToken")
            if not page_token:
                # historyId describes the whole result, not the processed page.
                # Failed later pages must replay from the original checkpoint.
                account.history_cursor = str(page.get("historyId", cursor))
                break

    async def _store(
        self,
        account: MailAccount,
        message: dict[str, Any],
        run: SyncRun,
    ) -> None:
        run.messages_seen += 1
        created = await self.repository.upsert_message(message_values(account, message))
        await self.repository.queue_analysis(
            account.id,
            message["id"],
            account.tenant_id,
        )
        if created:
            run.messages_created += 1
        else:
            run.messages_updated += 1
