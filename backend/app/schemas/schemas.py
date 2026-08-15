"""Schemas Pydantic (entrada/salida de la API)."""

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class TwoFactorSetupIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class TwoFactorConfirmIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class TwoFactorDisableIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    is_admin: bool
    totp_enabled: bool = False


class SyncEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    account_email: str
    status: str
    messages_found: int
    new_messages: int
    duration_ms: int
    error: str
    created_at: datetime


# --- Cuentas de correo ---
class MailAccountIn(BaseModel):
    email: EmailStr
    provider: Literal["outlook", "hotmail", "gmail", "custom"] = "custom"
    imap_host: str = Field(min_length=1, max_length=253)
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_user: str | None = Field(default=None, max_length=320)
    password: str | None = Field(
        None,
        min_length=1,
        max_length=256,
        description="Solo para proveedores que todavía aceptan contraseña",
    )

    @field_validator("imap_host")
    @classmethod
    def normalize_host(cls, value: str) -> str:
        host = value.strip().lower().rstrip(".")
        if not host or any(character.isspace() for character in host):
            raise ValueError("invalid IMAP host")
        return host

class MailAccountUpdate(BaseModel):
    imap_host: str | None = Field(default=None, min_length=1, max_length=253)
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_user: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    is_enabled: bool | None = None

    @field_validator("imap_host")
    @classmethod
    def normalize_optional_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        host = value.strip().lower().rstrip(".")
        if not host or any(character.isspace() for character in host):
            raise ValueError("invalid IMAP host")
        return host


class MailAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    provider: str
    imap_host: str
    imap_port: int
    is_enabled: bool
    last_synced_at: datetime | None
    last_status: str
    last_error: str
    auth_method: str
    oauth_connected: bool = False


# --- Mensajes ---
class MessageListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    from_name: str
    from_addr: str
    subject: str
    snippet: str
    received_at: datetime
    is_alert: bool
    sender_trusted: bool
    security_warning: str


class MessageDetail(MessageListItem):
    to_addr: str
    body_text: str
    body_html: str


class PaginatedMessages(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MessageListItem]


# --- Alertas ---
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service: str
    keyword: str
    severity: str
    resolved: bool
    created_at: datetime
    message: MessageListItem


class PaginatedAlerts(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AlertOut]


class StatsOut(BaseModel):
    accounts_total: int
    accounts_ok: int
    accounts_error: int
    messages_total: int
    alerts_open: int


# --- Suscripciones ---
class SubscriptionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message_id: int | None
    previous_status: str
    status: str
    severity: str
    reason: str
    score: int
    detected_at: datetime


class SubscriptionOut(BaseModel):
    id: int
    account_id: int
    account_email: EmailStr
    service: str
    status: str
    severity: str
    reason: str
    score: int
    latest_message_id: int | None
    detected_at: datetime
    updated_at: datetime


class SubscriptionDetail(SubscriptionOut):
    events: list[SubscriptionEventOut]


class SubscriptionStatsOut(BaseModel):
    total: int
    active: int
    warning: int
    payment_failed: int
    suspended: int
    cancelled: int
