from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mail_control.infrastructure.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class MailProvider(StrEnum):
    GMAIL = "gmail"
    MICROSOFT = "microsoft"


class AccountStatus(StrEnum):
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    REAUTH_REQUIRED = "reauth_required"
    DISCONNECTED = "disconnected"


class SyncKind(StrEnum):
    INITIAL = "initial"
    INCREMENTAL = "incremental"


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MailAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mail_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "provider_account_id"),
        Index("ix_mail_accounts_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connected_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[MailProvider] = mapped_column(
        Enum(MailProvider, name="mail_provider"),
        nullable=False,
    )
    provider_account_id: Mapped[str] = mapped_column(String(320), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"),
        default=AccountStatus.CONNECTED,
        nullable=False,
    )
    history_cursor: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list[EmailMessage]] = relationship(back_populates="account")
    gmail_watch_state: Mapped[GmailWatchState | None] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    microsoft_graph_subscription: Mapped[MicrosoftGraphSubscription | None] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class EmailMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("mail_account_id", "provider_message_id"),
        Index("ix_email_messages_tenant_received", "tenant_id", "received_at"),
        Index("ix_email_messages_account_thread", "mail_account_id", "thread_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(255))
    history_id: Mapped[str | None] = mapped_column(String(64))
    internet_message_id: Mapped[str | None] = mapped_column(String(998))
    sender: Mapped[str | None] = mapped_column(String(998))
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    internal_date_ms: Mapped[int | None] = mapped_column(BigInteger)
    size_estimate: Mapped[int | None] = mapped_column(Integer)
    label_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mailbox: Mapped[str] = mapped_column(String(16), default="inbox", nullable=False)

    account: Mapped[MailAccount] = relationship(back_populates="messages")


class SyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_tenant_started", "tenant_id", "started_at"),
        Index("ix_sync_runs_account_status", "mail_account_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[SyncKind] = mapped_column(Enum(SyncKind, name="sync_kind"), nullable=False)
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    messages_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class MailSyncCursor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mail_sync_cursors"
    __table_args__ = (
        UniqueConstraint("mail_account_id", "resource_key"),
        Index("ix_mail_sync_cursors_tenant_account", "tenant_id", "mail_account_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_key: Mapped[str] = mapped_column(String(512), nullable=False)
    cursor: Mapped[str] = mapped_column(Text, nullable=False)


class GmailWatchState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gmail_watch_states"
    __table_args__ = (
        UniqueConstraint("mail_account_id"),
        Index("ix_gmail_watch_states_tenant_due", "tenant_id", "expiration_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    history_id: Mapped[str | None] = mapped_column(String(64))
    expiration_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)

    account: Mapped[MailAccount] = relationship(back_populates="gmail_watch_state")


class MicrosoftGraphSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "microsoft_graph_subscriptions"
    __table_args__ = (
        UniqueConstraint("mail_account_id"),
        UniqueConstraint("subscription_id"),
        Index("ix_microsoft_graph_subscriptions_tenant_due", "tenant_id", "expiration_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id: Mapped[str | None] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(255), default="me/messages", nullable=False)
    client_state: Mapped[str] = mapped_column(String(128), nullable=False)
    expiration_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)

    account: Mapped[MailAccount] = relationship(
        back_populates="microsoft_graph_subscription"
    )
