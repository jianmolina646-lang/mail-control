from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast

import structlog

from mail_control.modules.mail.auth_state import AccountAuthorizationChanged
from mail_control.modules.mail.gmail import (
    GmailClient,
    GmailHistoryExpired,
    GmailMessageNotFound,
    GmailReauthRequired,
    GmailTransientError,
)
from mail_control.modules.mail.imap import GmailImapClient
from mail_control.modules.mail.models import (
    AccountStatus,
    MailAccount,
    MailProvider,
    MailSyncCursor,
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
        if not await self.repository.update_account_state(
            account, {"status": AccountStatus.SYNCING},
        ):
            raise AccountAuthorizationChanged("Account changed before synchronization")
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
            if not await self.repository.update_account_state(account, {
                "status": AccountStatus.CONNECTED, "last_error": None,
                "last_synced_at": datetime.now(UTC), "history_cursor": account.history_cursor,
            }):
                raise AccountAuthorizationChanged("Account changed during synchronization")
        except Exception as error:
            run.status = SyncStatus.FAILED
            run.error = str(error)[:2000]
            if not isinstance(error, AccountAuthorizationChanged):
                applied = await self.repository.update_account_state(account, {
                    "status": AccountStatus.REAUTH_REQUIRED
                    if isinstance(error, GmailReauthRequired) else AccountStatus.ERROR,
                    "last_error": run.error,
                }, error)
                if not applied:
                    raise AccountAuthorizationChanged("Account authorization changed") from error
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
        pending = await self.repository.cursor(
            account.tenant_id, account.id, "gmail:initial",
        )
        # A separate checkpoint belongs to the *whole* import, not an attempt.
        # Advancing it on a retry loses changes to messages we already imported.
        for attempt in range(2):
            existing_ids = await self.repository.active_provider_message_ids(account.id)
            state = self._initial_state(pending)
            if state is None:
                baseline = (await client.profile()).get("historyId")
                if not baseline:
                    raise GmailTransientError("Gmail omitted the initial history checkpoint")
                state = (str(baseline), bool(existing_ids))
                value = json.dumps({
                    "history_id": state[0], "refresh_existing": state[1],
                })
                if pending is None:
                    pending = MailSyncCursor(
                        tenant_id=account.tenant_id,
                        mail_account_id=account.id,
                        resource_key="gmail:initial",
                        cursor=value,
                    )
                    self.repository.add(pending)
                else:
                    pending.cursor = value
            baseline, refresh_existing = state
            seen_ids: set[str] = set()
            page_token: str | None = None
            while True:
                page = await client.list_messages(page_token=page_token)
                for item in page.get("messages", []):
                    message_id = item["id"]
                    seen_ids.add(message_id)
                    if not refresh_existing and message_id in existing_ids:
                        continue
                    await self._refresh_message(account, client, message_id, run)
                page_token = page.get("nextPageToken")
                # Persist the import baseline together with each completed page.
                # Only attempts sharing it may skip previously stored messages.
                await self.repository.checkpoint(account.tenant_id)
                if not page_token:
                    break

            # Absence from a changing, paginated listing is not proof of deletion.
            # This also reconciles deletions older than Gmail's retained history.
            for message_id in existing_ids - seen_ids:
                await self._refresh_message(account, client, message_id, run)

            try:
                next_cursor = await self._replay_history(account, client, run, baseline)
            except GmailHistoryExpired:
                # An expired baseline cannot justify skipping old records. Persist
                # an invalid marker even if the replacement attempt also fails.
                cast(MailSyncCursor, pending).cursor = ""
                if attempt == 1:
                    raise GmailTransientError(
                        "Gmail history expired during the full import"
                    ) from None
                continue
            account.history_cursor = next_cursor
            await self.repository.delete_cursor(cast(MailSyncCursor, pending))
            return

    @staticmethod
    def _initial_state(pending: MailSyncCursor | None) -> tuple[str, bool] | None:
        if pending is None:
            return None
        try:
            state = json.loads(pending.cursor)
        except (TypeError, ValueError):
            return None
        if (
            not isinstance(state, dict)
            or not isinstance(state.get("history_id"), str)
            or not state["history_id"]
            or not isinstance(state.get("refresh_existing"), bool)
        ):
            return None
        return state["history_id"], state["refresh_existing"]

    async def _refresh_message(
        self, account: MailAccount, client: GmailClient, message_id: str, run: SyncRun,
    ) -> None:
        try:
            message = await client.get_message(message_id, full=True)
        except GmailMessageNotFound:
            await self.repository.mark_deleted(account.id, message_id, datetime.now(UTC))
            logger.info(
                "gmail_message_missing_during_sync",
                account_id=str(account.id),
                sync_kind=run.kind.value,
            )
            return
        await self._store(account, message, run)

    async def _incremental_sync(
        self,
        account: MailAccount,
        client: GmailClient,
        run: SyncRun,
    ) -> None:
        assert account.history_cursor is not None
        account.history_cursor = await self._replay_history(
            account, client, run, account.history_cursor,
        )

    async def _replay_history(
        self, account: MailAccount, client: GmailClient, run: SyncRun, cursor: str,
    ) -> str:
        page_token: str | None = None
        while True:
            page = await client.history(cursor, page_token=page_token)
            message_ids = {
                change["message"]["id"]
                for history in page.get("history", [])
                for event in ("messagesAdded", "messagesDeleted", "labelsAdded", "labelsRemoved")
                for change in history.get(event, [])
            }
            for message_id in message_ids:
                await self._refresh_message(account, client, message_id, run)
            page_token = page.get("nextPageToken")
            if not page_token:
                # historyId describes the whole result, not the processed page.
                # Failed later pages must replay from the original checkpoint.
                return str(page.get("historyId", cursor))

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


class ImapSyncService(GmailSyncService):
    # This transport-specific subclass reuses storage, not the Gmail HTTP transport.
    async def synchronize(  # type: ignore[override]
        self, account: MailAccount, client: GmailImapClient,
    ) -> SyncRun:
        run = SyncRun(
            tenant_id=account.tenant_id, mail_account_id=account.id,
            kind=SyncKind.INCREMENTAL if account.history_cursor else SyncKind.INITIAL,
            status=SyncStatus.RUNNING, started_at=datetime.now(UTC),
        )
        self.repository.add(run)
        run.messages_seen = run.messages_created = run.messages_updated = 0
        if not await self.repository.update_account_state(
            account, {"status": AccountStatus.SYNCING},
        ):
            raise AccountAuthorizationChanged("Account changed before synchronization")
        await self.repository.flush()
        try:
            cursor = int(account.history_cursor) if account.history_cursor else None
            messages, next_cursor = await client.messages(cursor)
            for message in messages:
                await self._store(account, message, run)
            if next_cursor is not None:
                account.history_cursor = str(next_cursor)
            run.status = SyncStatus.SUCCEEDED
            if not await self.repository.update_account_state(account, {
                "status": AccountStatus.CONNECTED, "last_error": None,
                "last_synced_at": datetime.now(UTC), "history_cursor": account.history_cursor,
            }):
                raise AccountAuthorizationChanged("Account changed during synchronization")
        except Exception as error:
            run.status = SyncStatus.FAILED
            run.error = str(error)[:2000]
            if not isinstance(error, AccountAuthorizationChanged):
                applied = await self.repository.update_account_state(account, {
                    "status": AccountStatus.ERROR, "last_error": run.error,
                }, error)
                if not applied:
                    raise AccountAuthorizationChanged("Account authorization changed") from error
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            await self.repository.commit()
        return run
