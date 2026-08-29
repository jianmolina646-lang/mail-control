from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, database_session, require_role
from mail_control.modules.identity.models import RoleName, User
from mail_control.modules.identity.security import hash_password
from mail_control.modules.mail.models import EmailMessage, MailAccount
from mail_control.modules.saas.models import Plan, TenantSubscription
from mail_control.modules.saas.schemas import (
    CreateWorkspaceUser,
    PlanUsage,
    UpdateWorkspaceUser,
    WorkspaceUser,
)

router = APIRouter(prefix="/v1/saas", tags=["saas"])
Admin = Annotated[Principal, Depends(require_role(RoleName.ADMIN))]
Session = Annotated[AsyncSession, Depends(database_session)]


def validate_managed_role(principal: Principal, role: RoleName) -> None:
    """Prevent privilege escalation and preserve the single workspace owner."""
    if role == RoleName.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner role cannot be assigned")
    if principal.user.role == RoleName.ADMIN and role == RoleName.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admins cannot assign admin role")


def validate_managed_user(principal: Principal, user: User) -> None:
    if user.role == RoleName.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "workspace owner cannot be modified")
    if principal.user.role == RoleName.ADMIN and user.role == RoleName.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admins cannot modify other admins")


@router.get("/usage", response_model=PlanUsage)
async def usage(principal: Admin, session: Session) -> PlanUsage:
    tenant_id = principal.claims.tenant_id
    subscription = (await session.execute(
        select(TenantSubscription, Plan).join(Plan).where(TenantSubscription.tenant_id == tenant_id)
    )).one_or_none()
    if subscription is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "workspace has no plan")
    current, plan = subscription
    month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    accounts = int(
        await session.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.tenant_id == tenant_id)
        )
        or 0
    )
    users = int(
        await session.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
        or 0
    )
    messages = int(
        await session.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.tenant_id == tenant_id,
                EmailMessage.created_at >= month,
            )
        )
        or 0
    )
    return PlanUsage(
        plan_code=plan.code, plan_name=plan.name, status=current.status,
        period_end=current.period_end, accounts=accounts,
        accounts_limit=plan.max_accounts, users=users,
        users_limit=plan.max_users, messages_this_month=messages,
        messages_limit=plan.max_messages_month,
    )


@router.get("/users", response_model=list[WorkspaceUser])
async def users(principal: Admin, session: Session) -> list[WorkspaceUser]:
    query = (
        select(User)
        .where(User.tenant_id == principal.claims.tenant_id)
        .order_by(User.created_at)
    )
    result = await session.scalars(query)
    return [WorkspaceUser.model_validate(user, from_attributes=True) for user in result]


@router.post("/users", response_model=WorkspaceUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: CreateWorkspaceUser,
    principal: Admin,
    session: Session,
) -> WorkspaceUser:
    tenant_id = principal.claims.tenant_id
    validate_managed_role(principal, data.role)
    limit = await session.scalar(
        select(Plan.max_users)
        .join(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
    )
    active_users = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )
    if limit is None or int(active_users or 0) >= limit:
        raise HTTPException(status.HTTP_409_CONFLICT, "plan user limit reached")
    normalized = data.email.strip().casefold()
    existing_user = await session.scalar(
        select(User.id).where(
            User.tenant_id == tenant_id,
            User.email_normalized == normalized,
        )
    )
    if existing_user:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already exists")
    user = User(
        tenant_id=tenant_id,
        email=data.email.strip(),
        email_normalized=normalized,
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return WorkspaceUser.model_validate(user, from_attributes=True)


@router.patch("/users/{user_id}", response_model=WorkspaceUser)
async def update_user(
    user_id: UUID,
    data: UpdateWorkspaceUser,
    principal: Admin,
    session: Session,
) -> WorkspaceUser:
    user = await session.scalar(
        select(User).where(
            User.tenant_id == principal.claims.tenant_id,
            User.id == user_id,
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    validate_managed_user(principal, user)
    if user.id == principal.user.id and data.is_active is False:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot deactivate current user")
    if data.role is not None:
        validate_managed_role(principal, data.role)
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    await session.commit()
    await session.refresh(user)
    return WorkspaceUser.model_validate(user, from_attributes=True)
