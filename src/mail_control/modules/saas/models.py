from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mail_control.infrastructure.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    max_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_messages_month: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TenantSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id"),
        Index("ix_tenant_subscriptions_status", "tenant_id", "status"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(String(20), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
