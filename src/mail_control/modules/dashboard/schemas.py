from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from mail_control.modules.analysis.models import AlertType, RiskLevel
from mail_control.modules.mail.models import AccountStatus, MailProvider


class AccountItem(BaseModel):
    id: UUID
    provider: MailProvider
    email: str
    status: AccountStatus
    last_synced_at: datetime | None
    last_error: str | None
    message_count: int
    alert_count: int


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
    mailbox: Literal["inbox", "archive", "trash"]
    thread_id: str | None


class MessageContent(BaseModel):
    id: UUID
    body: str | None
    body_html: str | None


class MessageStateUpdate(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None
    mailbox: Literal["inbox", "archive", "trash"] | None = None


class MessagePage(BaseModel):
    items: list[MessageItem]
    next_cursor: str | None


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
