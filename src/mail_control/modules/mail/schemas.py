from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mail_control.modules.mail.models import AccountStatus, MailProvider


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class AuthorizationRequest(BaseModel):
    account_id: UUID | None = None


class ImapConnectionRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    app_password: str = Field(min_length=16, max_length=64)


class MailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: MailProvider
    email: str
    status: AccountStatus
    last_synced_at: datetime | None
