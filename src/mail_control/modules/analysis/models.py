from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mail_control.infrastructure.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(StrEnum):
    PAYMENT_REJECTED = "payment_rejected"
    PAYMENT_METHOD_EXPIRED = "payment_method_expired"
    RENEWAL_DUE = "renewal_due"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_CHANGED = "email_changed"
    VERIFICATION_CODE = "verification_code"
    ACCESS_ATTEMPT = "access_attempt"
    SECURITY = "security"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class EmailAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_analyses"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    service: Mapped[str | None] = mapped_column(String(120))
    platform: Mapped[str | None] = mapped_column(String(120))
    amount: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(12))
    country: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    email_type: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    action_required: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level"), nullable=False
    )
    alert_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_tenant_created", "tenant_id", "created_at"),
        Index("ix_alerts_tenant_resolved", "tenant_id", "resolved_at"),
        Index(
            "uq_alerts_active_analysis_type",
            "analysis_id",
            "alert_type",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_analyses.id", ondelete="CASCADE"), nullable=False
    )
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, name="alert_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", create_type=False), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisIncident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Current state for one account, service and incident type.

    EmailAnalysis remains the immutable history. This row is the chronological
    projection used by operational views.
    """

    __tablename__ = "analysis_incidents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "mail_account_id",
            "service_key",
            "incident_type",
            name="uq_analysis_incidents_state_key",
        ),
        Index("ix_analysis_incidents_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE"), nullable=False
    )
    service_key: Mapped[str] = mapped_column(String(160), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_analyses.id", ondelete="CASCADE"), nullable=False
    )
    current_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(String(120))
    last_event_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_available", "status", "available_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus, name="outbox_status"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
