"""Schemas Pydantic (entrada/salida de la API)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    is_admin: bool


# --- Cuentas de correo ---
class MailAccountIn(BaseModel):
    email: EmailStr
    provider: str = "custom"
    imap_host: str
    imap_port: int = 993
    imap_user: str | None = None
    password: str | None = Field(
        None, description="Solo para proveedores que todavía aceptan contraseña"
    )


class MailAccountUpdate(BaseModel):
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    password: str | None = None
    is_enabled: bool | None = None


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
