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
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
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
    # App Password cifrada (Fernet). Nunca en texto plano.
    encrypted_password: Mapped[str] = mapped_column(Text)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="pending")  # ok/error/pending
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Message(Base):
    """Correo leído de una casilla. Solo lectura (visor)."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("account_id", "uid", name="uq_message_account_uid"),
        Index("ix_message_account_received", "account_id", "received_at"),
        Index("ix_message_received", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), index=True
    )
    uid: Mapped[str] = mapped_column(String(64))  # UID IMAP (por cuenta)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["MailAccount"] = relationship(back_populates="messages")
    alert: Mapped["Alert | None"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


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
