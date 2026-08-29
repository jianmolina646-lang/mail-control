from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import Principal, database_session, platform_admin
from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.identity.models import RoleName, Tenant, TenantStatus, User
from mail_control.modules.mail.models import EmailMessage, MailAccount
from mail_control.modules.saas.models import Plan, SubscriptionStatus, TenantSubscription
from mail_control.modules.saas.platform_schemas import (
    PlatformPlan,
    PlatformSummary,
    PlatformWorkspace,
    UpdatePlatformPlan,
    UpdatePlatformWorkspace,
)

router = APIRouter(prefix="/v1/platform", tags=["platform"])
PlatformAdmin = Annotated[Principal, Depends(platform_admin)]
Session = Annotated[AsyncSession, Depends(database_session)]


async def workspace_rows(session: AsyncSession) -> list[PlatformWorkspace]:
    tenants = list((await session.scalars(select(Tenant).order_by(Tenant.created_at.desc()))).all())
    month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result: list[PlatformWorkspace] = []
    for tenant in tenants:
        await set_tenant_context(session, tenant.id)
        subscription = (
            await session.execute(
                select(TenantSubscription, Plan)
                .join(Plan, Plan.id == TenantSubscription.plan_id)
                .where(TenantSubscription.tenant_id == tenant.id)
            )
        ).one_or_none()
        if subscription is None:
            continue
        current, plan = subscription
        owner_email = await session.scalar(
            select(User.email)
            .where(User.tenant_id == tenant.id, User.role == RoleName.OWNER)
            .order_by(User.created_at)
            .limit(1)
        )
        accounts = int(await session.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.tenant_id == tenant.id)
        ) or 0)
        users = int(await session.scalar(
            select(func.count(User.id)).where(User.tenant_id == tenant.id, User.is_active.is_(True))
        ) or 0)
        messages = int(await session.scalar(
            select(func.count(EmailMessage.id)).where(
                EmailMessage.tenant_id == tenant.id,
                EmailMessage.created_at >= month,
            )
        ) or 0)
        result.append(PlatformWorkspace(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            created_at=tenant.created_at,
            owner_email=owner_email,
            plan_code=plan.code,
            plan_name=plan.name,
            subscription_status=SubscriptionStatus(current.status),
            period_start=current.period_start,
            period_end=current.period_end,
            accounts=accounts,
            users=users,
            messages_this_month=messages,
        ))
    return result


@router.get("/summary", response_model=PlatformSummary)
async def summary(_: PlatformAdmin, session: Session) -> PlatformSummary:
    rows = await workspace_rows(session)
    return PlatformSummary(
        workspaces=len(rows),
        active_workspaces=sum(row.status == TenantStatus.ACTIVE for row in rows),
        trialing=sum(row.subscription_status == SubscriptionStatus.TRIALING for row in rows),
        past_due=sum(row.subscription_status == SubscriptionStatus.PAST_DUE for row in rows),
        connected_accounts=sum(row.accounts for row in rows),
        messages_this_month=sum(row.messages_this_month for row in rows),
    )


@router.get("/workspaces", response_model=list[PlatformWorkspace])
async def workspaces(_: PlatformAdmin, session: Session) -> list[PlatformWorkspace]:
    return await workspace_rows(session)


@router.get("/plans", response_model=list[PlatformPlan])
async def plans(_: PlatformAdmin, session: Session) -> list[PlatformPlan]:
    rows = (await session.scalars(select(Plan).order_by(Plan.max_accounts))).all()
    return [PlatformPlan.model_validate(row, from_attributes=True) for row in rows]


@router.patch("/workspaces/{tenant_id}", response_model=PlatformWorkspace)
async def update_workspace(
    tenant_id: UUID,
    data: UpdatePlatformWorkspace,
    _: PlatformAdmin,
    session: Session,
) -> PlatformWorkspace:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    await set_tenant_context(session, tenant_id)
    subscription = await session.scalar(
        select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    )
    if subscription is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "workspace has no subscription")
    if data.plan_code is not None:
        plan = await session.scalar(
            select(Plan).where(Plan.code == data.plan_code, Plan.is_active.is_(True))
        )
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "active plan not found")
        subscription.plan_id = plan.id
    if data.subscription_status is not None:
        subscription.status = data.subscription_status
    if data.tenant_status is not None:
        tenant.status = data.tenant_status
    if data.period_end is not None:
        if data.period_end <= subscription.period_start:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "period end must follow period start",
            )
        subscription.period_end = data.period_end
    await session.commit()
    rows = await workspace_rows(session)
    return next(row for row in rows if row.id == tenant_id)


@router.patch("/plans/{plan_id}", response_model=PlatformPlan)
async def update_plan(
    plan_id: UUID,
    data: UpdatePlatformPlan,
    _: PlatformAdmin,
    session: Session,
) -> PlatformPlan:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return PlatformPlan.model_validate(plan, from_attributes=True)
