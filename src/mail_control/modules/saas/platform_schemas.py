from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from mail_control.modules.identity.models import TenantStatus
from mail_control.modules.saas.models import SubscriptionStatus


class PlatformPlan(BaseModel):
    id: UUID
    code: str
    name: str
    max_accounts: int
    max_users: int
    max_messages_month: int
    is_active: bool


class PlatformWorkspace(BaseModel):
    id: UUID
    name: str
    slug: str
    status: TenantStatus
    created_at: datetime
    owner_email: str | None
    plan_code: str
    plan_name: str
    subscription_status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    accounts: int
    users: int
    messages_this_month: int


class PlatformSummary(BaseModel):
    workspaces: int
    active_workspaces: int
    trialing: int
    past_due: int
    connected_accounts: int
    messages_this_month: int


class UpdatePlatformWorkspace(BaseModel):
    plan_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=40,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    subscription_status: SubscriptionStatus | None = None
    tenant_status: TenantStatus | None = None
    period_end: datetime | None = None


class UpdatePlatformPlan(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    max_accounts: int | None = Field(default=None, ge=1, le=100000)
    max_users: int | None = Field(default=None, ge=1, le=100000)
    max_messages_month: int | None = Field(default=None, ge=100, le=1000000000)
    is_active: bool | None = None
