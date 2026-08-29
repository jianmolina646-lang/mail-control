from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mail_control.modules.identity.models import RoleName


class RegisterTenantRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=160)
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    owner_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("tenant_name", "owner_name")
    @classmethod
    def normalize_names(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("name is too short")
        return normalized

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


class LoginRequest(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        return RegisterTenantRequest.normalize_email(value)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=4096)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    role: RoleName
    is_platform_admin: bool = False


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
