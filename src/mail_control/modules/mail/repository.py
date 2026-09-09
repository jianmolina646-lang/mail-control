from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import ReturningInsert

from mail_control.modules.analysis.models import OutboxEvent, OutboxStatus
from mail_control.modules.mail.models import (
    EmailMessage,
    MailAccount,
    MailProvider,
    MailSyncCursor,
    SyncRun,
)


class MailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def account_by_provider_id(
        self,
        tenant_id: UUID,
        provider_account_id: str,
        provider: MailProvider,
    ) -> MailAccount | None:
        result = await self.session.scalar(
            select(MailAccount).where(
                MailAccount.tenant_id == tenant_id,
                MailAccount.provider_account_id == provider_account_id,
                MailAccount.provider == provider,
            )
        )
        return result

    async def account_by_id(
        self, tenant_id: UUID, account_id: UUID, provider: MailProvider | None = None
    ) -> MailAccount | None:
        statement = select(MailAccount).where(
            MailAccount.tenant_id == tenant_id, MailAccount.id == account_id
        )
        if provider is not None:
            statement = statement.where(MailAccount.provider == provider)
        result = await self.session.scalar(
            statement
        )
        return result

    async def cursor(
        self,
        tenant_id: UUID,
        account_id: UUID,
        resource_key: str,
    ) -> MailSyncCursor | None:
        return cast(
            MailSyncCursor | None,
            await self.session.scalar(
                select(MailSyncCursor).where(
                    MailSyncCursor.tenant_id == tenant_id,
                    MailSyncCursor.mail_account_id == account_id,
                    MailSyncCursor.resource_key == resource_key,
                )
            ),
        )

    def add(self, entity: MailAccount | MailSyncCursor | SyncRun) -> None:
        self.session.add(entity)

    async def mark_deleted(
        self,
        account_id: UUID,
        provider_message_id: str,
        deleted_at: datetime,
    ) -> None:
        await self.session.execute(
            update(EmailMessage)
            .where(
                EmailMessage.mail_account_id == account_id,
                EmailMessage.provider_message_id == provider_message_id,
            )
            .values(deleted_at=deleted_at)
        )

    async def upsert_message(self, values: dict[str, object]) -> bool:
        base_statement = insert(EmailMessage).values(**values)
        update_values: dict[str, Any] = {
            "thread_id": base_statement.excluded.thread_id,
            "history_id": base_statement.excluded.history_id,
            "label_ids": base_statement.excluded.label_ids,
            "payload": base_statement.excluded.payload,
            "snippet": base_statement.excluded.snippet,
            "deleted_at": None,
            "updated_at": base_statement.excluded.updated_at,
            "provider_folder_id": base_statement.excluded.provider_folder_id,
        }
        for field in ("is_read", "is_starred", "mailbox"):
            remote = getattr(base_statement.excluded, f"provider_{field}")
            update_values[f"provider_{field}"] = remote
            update_values[field] = func.coalesce(getattr(EmailMessage, f"local_{field}"), remote)
        for field in ("sender", "recipients", "subject", "received_at", "internet_message_id"):
            update_values[field] = getattr(base_statement.excluded, field)
        statement: ReturningInsert[tuple[bool]] = base_statement.on_conflict_do_update(
            index_elements=["mail_account_id", "provider_message_id"],
            set_=update_values,
        ).returning(literal_column("xmax = 0"))
        return bool(await self.session.scalar(statement))

    async def queue_analysis(
        self,
        account_id: UUID,
        provider_message_id: str,
        tenant_id: UUID,
    ) -> None:
        message_id = await self.session.scalar(
            select(EmailMessage.id).where(
                EmailMessage.mail_account_id == account_id,
                EmailMessage.provider_message_id == provider_message_id,
            )
        )
        if message_id is None:
            raise RuntimeError("message upsert did not return a persisted record")
        statement = insert(OutboxEvent).values(
            tenant_id=tenant_id,
            aggregate_id=message_id,
            event_type="email.analysis.requested",
            dedupe_key=f"email-analysis:{message_id}",
            payload={"email_message_id": str(message_id)},
            status=OutboxStatus.PENDING,
            attempts=0,
            available_at=datetime.now(UTC),
        )
        await self.session.execute(
            statement.on_conflict_do_nothing(index_elements=["dedupe_key"])
        )

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
