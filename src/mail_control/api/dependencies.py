from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.identity.models import RoleName, User
from mail_control.modules.identity.repository import IdentityRepository
from mail_control.modules.identity.security import AccessClaims, decode_access_token
from mail_control.settings import get_settings

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@dataclass(frozen=True, slots=True)
class Principal:
    claims: AccessClaims
    user: User


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.resources.database.session():
        yield session


async def system_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.resources.system_database.session():
        yield session


async def current_principal(
    credentials: BearerCredentials,
    session: Annotated[AsyncSession, Depends(database_session)],
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    try:
        claims = decode_access_token(get_settings(), credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid access token",
        ) from None

    await set_tenant_context(session, claims.tenant_id)
    user = await IdentityRepository(session).user_by_id(claims.tenant_id, claims.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "inactive user")
    return Principal(claims=claims, user=user)


ROLE_RANK = {
    RoleName.VIEWER: 10,
    RoleName.OPERATOR: 20,
    RoleName.ADMIN: 30,
    RoleName.OWNER: 40,
}


def require_role(minimum: RoleName) -> Callable[[Principal], Awaitable[Principal]]:
    async def dependency(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if ROLE_RANK[principal.user.role] < ROLE_RANK[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient permissions")
        return principal

    return dependency


async def platform_admin(
    principal: Annotated[Principal, Depends(current_principal)],
) -> Principal:
    if not principal.user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "platform administrator required")
    return principal
