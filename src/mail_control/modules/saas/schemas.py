from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from mail_control.modules.identity.models import RoleName


class PlanUsage(BaseModel):
    plan_code: str
    plan_name: str
    status: str
    period_end: datetime
    accounts: int
    accounts_limit: int
    users: int
    users_limit: int
    messages_this_month: int
    messages_limit: int


class WorkspaceUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: RoleName
    is_active: bool
    last_login_at: datetime | None


class CreateWorkspaceUser(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    role: RoleName = RoleName.VIEWER

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized.count("@") != 1 or any(character.isspace() for character in normalized):
            raise ValueError("invalid email address")
        local, domain = normalized.rsplit("@", 1)
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("invalid email address")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("display name is too short")
        return normalized


class UpdateWorkspaceUser(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None
