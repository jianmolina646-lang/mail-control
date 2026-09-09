from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from mail_control.modules.analysis.models import AlertType, RiskLevel
from mail_control.modules.mail.models import AccountStatus, MailProvider

Mailbox = Literal["inbox", "archive", "trash", "sent", "drafts", "spam", "other"]


class AccountItem(BaseModel):
    id: UUID
    provider: MailProvider
    email: str
    status: AccountStatus
    last_synced_at: datetime | None
    last_error: str | None
    message_count: int
    alert_count: int
    unread_count: int = 0
    folder_counts: dict[str, int] = Field(default_factory=dict)


class MessageItem(BaseModel):
    id: UUID
    account_id: UUID
    provider: MailProvider
    account_email: str
    sender: str | None
    subject: str | None
    snippet: str | None
    body: str | None
    body_html: str | None
    received_at: datetime | None
    category: str | None
    risk_level: RiskLevel | None
    alert_count: int
    is_read: bool
    is_starred: bool
    mailbox: Mailbox
    thread_id: str | None


class AttachmentItem(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    content_id: str | None = None
    is_inline: bool = False
    download_url: str
    inline_url: str | None = None


class MessageContent(BaseModel):
    id: UUID
    body: str | None
    body_html: str | None
    account_id: UUID | None = None
    provider: MailProvider | None = None
    account_email: str | None = None
    sender: str | None = None
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str | None = None
    received_at: datetime | None = None
    is_read: bool = False
    is_starred: bool = False
    mailbox: Mailbox = "inbox"
    thread_id: str | None = None
    attachments: list[AttachmentItem] = Field(default_factory=list)
    content_warning: str | None = None
    attachments_error: str | None = None


class ThreadPage(BaseModel):
    items: list[MessageContent]
    next_cursor: str | None
    total_count: int


class MessageCounts(BaseModel):
    total: int = 0
    unread: int = 0
    starred: int = 0
    critical: int = 0
    unanalyzed: int = 0
    categories: dict[str, int] = Field(default_factory=dict)
    folder_counts: dict[str, int] = Field(default_factory=dict)
    archive: int = 0
    trash: int = 0


class MessageStateUpdate(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None
    mailbox: Mailbox | None = None


class MessagePage(BaseModel):
    items: list[MessageItem]
    next_cursor: str | None
    total_count: int = 0
    unread_count: int = 0


class AnalysisItem(BaseModel):
    id: UUID
    message_id: UUID
    account_email: str
    sender: str | None
    subject: str | None
    service: str | None
    platform: str | None
    amount: str | None
    currency: str | None
    country: str | None
    language: str
    priority: str
    email_type: str
    category: str
    action_required: str | None
    risk_level: RiskLevel
    alert_types: list[str]
    model: str
    prompt_version: str
    created_at: datetime


class AnalysisPage(BaseModel):
    items: list[AnalysisItem]
    next_cursor: str | None


class AlertItem(BaseModel):
    id: UUID
    message_id: UUID
    alert_type: AlertType
    title: str
    detail: str | None
    risk_level: RiskLevel
    created_at: datetime
    resolved_at: datetime | None


class AlertPage(BaseModel):
    items: list[AlertItem]
    next_cursor: str | None


class DailyMetric(BaseModel):
    day: date
    messages: int
    alerts: int


class DashboardSummary(BaseModel):
    connected_accounts: int
    total_messages: int
    analyzed_messages: int
    open_alerts: int
    critical_alerts: int
    messages_last_24h: int
    analysis_coverage_percent: float = Field(ge=0, le=100)
    trend: list[DailyMetric]
