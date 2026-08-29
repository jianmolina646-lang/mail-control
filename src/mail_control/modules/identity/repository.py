from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.modules.identity.models import RefreshSession, Tenant, User


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def tenant_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.scalar(select(Tenant).where(Tenant.slug == slug))
        return result

    async def user_by_email(self, tenant_id: UUID, email: str) -> User | None:
        statement = select(User).where(
            User.tenant_id == tenant_id,
            User.email_normalized == email.strip().casefold(),
        )
        return cast(User | None, await self.session.scalar(statement))

    async def user_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        statement = select(User).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
        return cast(User | None, await self.session.scalar(statement))

    async def refresh_session(self, token_hash: str) -> RefreshSession | None:
        return cast(
            RefreshSession | None,
            await self.session.scalar(
                select(RefreshSession).where(RefreshSession.token_hash == token_hash)
            ),
        )

    def add(self, entity: Tenant | User | RefreshSession) -> None:
        self.session.add(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def flush(self) -> None:
        await self.session.flush()

    async def revoke_session(self, session: RefreshSession, revoked_at: datetime) -> None:
        session.revoked_at = revoked_at
        await self.session.flush()
