from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mail_control.modules.mail.microsoft import (
    MicrosoftDeltaExpired,
    MicrosoftGraphClient,
    MicrosoftTransientError,
)
from mail_control.modules.mail.models import (
    AccountStatus,
    MailAccount,
    MailSyncCursor,
    SyncKind,
    SyncRun,
    SyncStatus,
)
from mail_control.modules.mail.repository import MailRepository


def recipient_addresses(message: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for field in ("toRecipients", "ccRecipients", "bccRecipients"):
        for recipient in message.get(field, []):
            address = recipient.get("emailAddress", {}).get("address")
            if address:
                result.append(address)
    return result


def microsoft_message_values(
    account: MailAccount,
    message: dict[str, Any],
) -> dict[str, object]:
    sender = message.get("from", {}).get("emailAddress", {})
    received = message.get("receivedDateTime")
    return {
        "tenant_id": account.tenant_id,
        "mail_account_id": account.id,
        "provider_message_id": message["id"],
        "thread_id": message.get("conversationId"),
        "history_id": None,
        "internet_message_id": message.get("internetMessageId"),
        "sender": sender.get("address"),
        "recipients": recipient_addresses(message),
        "subject": message.get("subject"),
        "snippet": message.get("bodyPreview"),
        "received_at": datetime.fromisoformat(received.replace("Z", "+00:00"))
        if received
        else None,
        "internal_date_ms": None,
        "size_estimate": None,
        "label_ids": [message.get("parentFolderId", "")],
        "payload": message,
        "deleted_at": None,
    }


class MicrosoftSyncService:
    def __init__(self, repository: MailRepository) -> None:
        self.repository = repository

    async def synchronize(
        self,
        account: MailAccount,
        client: MicrosoftGraphClient,
    ) -> SyncRun:
        run = SyncRun(
            tenant_id=account.tenant_id,
            mail_account_id=account.id,
            kind=SyncKind.INCREMENTAL,
            status=SyncStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.repository.add(run)
        previous_status = account.status
        account.status = AccountStatus.SYNCING
        await self.repository.flush()
        try:
            folders = await self._all_folders(client)
            had_cursor = False
            for folder in folders:
                resource_key = f"folder:{folder['id']}"
                cursor = await self.repository.cursor(
                    account.tenant_id,
                    account.id,
                    resource_key,
                )
                had_cursor = had_cursor or cursor is not None
                await self._sync_folder(account, client, folder["id"], cursor, run)
            run.kind = SyncKind.INCREMENTAL if had_cursor else SyncKind.INITIAL
            run.status = SyncStatus.SUCCEEDED
            account.status = AccountStatus.CONNECTED
            account.last_error = None
            account.last_synced_at = datetime.now(UTC)
        except MicrosoftTransientError as error:
            run.status = SyncStatus.FAILED
            run.error = str(error)[:2000]
            account.status = (
                previous_status
                if previous_status is not AccountStatus.SYNCING
                else AccountStatus.CONNECTED
            )
            account.last_error = run.error
            raise
        except Exception as error:
            run.status = SyncStatus.FAILED
            run.error = str(error)[:2000]
            account.status = AccountStatus.ERROR
            account.last_error = run.error
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            await self.repository.commit()
        return run

    async def _all_folders(self, client: MicrosoftGraphClient) -> list[dict[str, Any]]:
        folders: list[dict[str, Any]] = []
        next_link: str | None = None
        while True:
            page = await client.folders(next_link)
            folders.extend(page.get("value", []))
            next_link = page.get("@odata.nextLink")
            if not next_link:
                break
        queue = [folder for folder in folders if folder.get("childFolderCount", 0)]
        while queue:
            parent = queue.pop()
            page_url: str | None = (
                f"/me/mailFolders/{parent['id']}/childFolders"
                "?includeHiddenFolders=true&$top=100"
            )
            while page_url:
                page = await client.get(page_url)
                children = page.get("value", [])
                folders.extend(children)
                queue.extend(
                    child for child in children if child.get("childFolderCount", 0)
                )
                page_url = page.get("@odata.nextLink")
        return folders

    async def _sync_folder(
        self,
        account: MailAccount,
        client: MicrosoftGraphClient,
        folder_id: str,
        cursor: MailSyncCursor | None,
        run: SyncRun,
    ) -> None:
        resource_key = f"folder:{folder_id}"
        next_link = cursor.cursor if cursor else None
        try:
            while True:
                page = await client.delta(folder_id, next_link)
                for message in page.get("value", []):
                    run.messages_seen += 1
                    if "@removed" in message:
                        await self.repository.mark_deleted(
                            account.id,
                            message["id"],
                            datetime.now(UTC),
                        )
                        run.messages_updated += 1
                    else:
                        created = await self.repository.upsert_message(
                            microsoft_message_values(account, message)
                        )
                        await self.repository.queue_analysis(
                            account.id,
                            message["id"],
                            account.tenant_id,
                        )
                        if created:
                            run.messages_created += 1
                        else:
                            run.messages_updated += 1
                next_link = page.get("@odata.nextLink")
                delta_link = page.get("@odata.deltaLink")
                if delta_link:
                    if cursor is None:
                        cursor = MailSyncCursor(
                            tenant_id=account.tenant_id,
                            mail_account_id=account.id,
                            resource_key=resource_key,
                            cursor=delta_link,
                        )
                        self.repository.add(cursor)
                    else:
                        cursor.cursor = delta_link
                    break
                if not next_link:
                    raise RuntimeError("Microsoft delta response omitted its continuation")
        except MicrosoftDeltaExpired:
            if cursor is not None:
                await self.repository.session.delete(cursor)
                await self.repository.flush()
            await self._sync_folder(account, client, folder_id, None, run)
