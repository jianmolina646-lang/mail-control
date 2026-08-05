"""Modelos de base de datos."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Operador del panel."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_code_hashes: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MailAccount(Base):
    """Casilla IMAP a monitorear. La contraseña se guarda ENCRIPTADA."""

    __tablename__ = "mail_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="custom")  # outlook/gmail/custom
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_user: Mapped[str] = mapped_column(String(255))
    # Solo se usa para proveedores legacy/custom; Microsoft usa OAuth2.
    encrypted_password: Mapped[str] = mapped_column(Text, default="")
    auth_method: Mapped[str] = mapped_column(String(20), default="password")
    # Caché MSAL cifrada. Contiene los tokens necesarios para renovación silenciosa.
    encrypted_oauth_cache: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="pending")  # ok/error/pending
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    sync_events: Mapped[list["SyncEvent"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    @property
    def oauth_connected(self) -> bool:
        return bool(self.encrypted_oauth_cache)


class Message(Base):
    """Correo leído de una casilla. Solo lectura (visor)."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "folder_name", "uid",
            name="uq_message_account_folder_uid",
        ),
        Index("ix_message_account_received", "account_id", "received_at"),
        Index("ix_message_received", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), index=True
    )
    uid: Mapped[str] = mapped_column(String(64))  # UID IMAP (por cuenta)
    folder_name: Mapped[str] = mapped_column(String(512), default="INBOX")
    message_id: Mapped[str] = mapped_column(String(512), default="")
    from_addr: Mapped[str] = mapped_column(String(512), default="")
    from_name: Mapped[str] = mapped_column(String(255), default="")
    to_addr: Mapped[str] = mapped_column(String(512), default="")
    subject: Mapped[str] = mapped_column(String(1000), default="")
    snippet: Mapped[str] = mapped_column(String(500), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    is_alert: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sender_trusted: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    security_warning: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["MailAccount"] = relationship(back_populates="messages")
    alert: Mapped["Alert | None"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


class SyncEvent(Base):
    """Resultado persistente de cada intento de sincronización."""

    __tablename__ = "sync_events"
    __table_args__ = (
        Index("ix_sync_event_account_created", "account_id", "created_at"),
        Index("ix_sync_event_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    messages_found: Mapped[int] = mapped_column(Integer, default=0)
    new_messages: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["MailAccount"] = relationship(back_populates="sync_events")


class AgentCodeReceipt(Base):
    """Registra códigos entregados al agente para impedir su reutilización."""

    __tablename__ = "agent_code_receipts"
    __table_args__ = (
        UniqueConstraint("message_id", "code_hash", name="uq_agent_code_message_hash"),
        Index("ix_agent_code_job", "job_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Alert(Base):
    """Alerta crítica de suscripción (radar de streaming)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True, index=True
    )
    service: Mapped[str] = mapped_column(String(50), default="")  # netflix/hbomax/...
    keyword: Mapped[str] = mapped_column(String(50), default="")  # pago/rechazado/...
    severity: Mapped[str] = mapped_column(String(20), default="critical")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    message: Mapped["Message"] = relationship(back_populates="alert")


class Subscription(Base):
    """Último estado conocido de un servicio para una cuenta de correo."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("account_id", "service", name="uq_subscription_account_service"),
        Index("ix_subscription_status_updated", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), index=True
    )
    service: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    reason: Mapped[str] = mapped_column(String(255), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    latest_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    account: Mapped["MailAccount"] = relationship(back_populates="subscriptions")
    latest_message: Mapped["Message | None"] = relationship(
        foreign_keys=[latest_message_id]
    )
    events: Mapped[list["SubscriptionEvent"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="SubscriptionEvent.detected_at.desc()",
    )


class SubscriptionEvent(Base):
    """Historial inmutable de cambios de estado de una suscripción."""

    __tablename__ = "subscription_events"
    __table_args__ = (
        Index("ix_subscription_event_timeline", "subscription_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    previous_status: Mapped[str] = mapped_column(String(30), default="unknown")
    status: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(20), default="info")
    reason: Mapped[str] = mapped_column(String(255), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    subscription: Mapped["Subscription"] = relationship(back_populates="events")
    message: Mapped["Message | None"] = relationship(foreign_keys=[message_id])
