from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.modules.analysis.models import Alert, AnalysisIncident, EmailAnalysis, RiskLevel
from mail_control.modules.dashboard.cursor import decode_cursor, encode_cursor
from mail_control.modules.dashboard.schemas import (
    AccountItem,
    AlertItem,
    AlertPage,
    AnalysisItem,
    AnalysisPage,
    DailyMetric,
    DashboardSummary,
    MessageItem,
    MessagePage,
)
from mail_control.modules.mail.models import (
    AccountStatus,
    EmailMessage,
    MailAccount,
    MailProvider,
)


class DashboardRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def accounts(self) -> list[AccountItem]:
        message_counts = (
            select(
                EmailMessage.mail_account_id.label("account_id"),
                func.count(EmailMessage.id).label("message_count"),
            )
            .where(EmailMessage.tenant_id == self.tenant_id)
            .group_by(EmailMessage.mail_account_id)
            .subquery()
        )
        alert_counts = (
            select(
                EmailMessage.mail_account_id.label("account_id"),
                func.count(Alert.id).label("alert_count"),
            )
            .join(Alert, Alert.email_message_id == EmailMessage.id)
            .where(
                EmailMessage.tenant_id == self.tenant_id,
                Alert.resolved_at.is_(None),
            )
            .group_by(EmailMessage.mail_account_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    MailAccount.id,
                    MailAccount.provider,
                    MailAccount.email,
                    MailAccount.status,
                    MailAccount.last_synced_at,
                    MailAccount.last_error,
                    func.coalesce(message_counts.c.message_count, 0),
                    func.coalesce(alert_counts.c.alert_count, 0),
                )
                .outerjoin(message_counts, message_counts.c.account_id == MailAccount.id)
                .outerjoin(alert_counts, alert_counts.c.account_id == MailAccount.id)
                .where(MailAccount.tenant_id == self.tenant_id)
                .order_by(MailAccount.email)
            )
        ).all()
        return [
            AccountItem(
                id=row[0],
                provider=row[1],
                email=row[2],
                status=row[3],
                last_synced_at=row[4],
                last_error=row[5],
                message_count=row[6],
                alert_count=row[7],
            )
            for row in rows
        ]

    async def messages(
        self,
        *,
        search: str | None,
        account_id: UUID | None,
        provider: MailProvider | None,
        category: str | None,
        risk_level: RiskLevel | None,
        mailbox: str,
        cursor: str | None,
        limit: int,
    ) -> MessagePage:
        sort_time = func.coalesce(EmailMessage.received_at, EmailMessage.created_at)
        alert_counts = (
            select(
                Alert.email_message_id.label("message_id"),
                func.count(Alert.id).label("alert_count"),
            )
            .where(Alert.tenant_id == self.tenant_id)
            .group_by(Alert.email_message_id)
            .subquery()
        )
        statement = (
            select(
                EmailMessage.id,
                EmailMessage.mail_account_id,
                MailAccount.provider,
                MailAccount.email,
                EmailMessage.sender,
                EmailMessage.subject,
                EmailMessage.snippet,
                EmailMessage.received_at,
                EmailAnalysis.category,
                EmailAnalysis.risk_level,
                func.coalesce(alert_counts.c.alert_count, 0),
                EmailMessage.is_read,
                EmailMessage.is_starred,
                EmailMessage.mailbox,
                EmailMessage.thread_id,
                sort_time.label("sort_time"),
            )
            .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
            .outerjoin(EmailAnalysis, EmailAnalysis.email_message_id == EmailMessage.id)
            .outerjoin(alert_counts, alert_counts.c.message_id == EmailMessage.id)
            .where(
                EmailMessage.tenant_id == self.tenant_id,
                EmailMessage.deleted_at.is_(None),
                EmailMessage.mailbox == mailbox,
            )
        )
        if search:
            statement = statement.where(
                text(
                    "email_messages.search_vector "
                    "@@ websearch_to_tsquery('simple', :search)"
                ).bindparams(search=search)
            )
        if account_id:
            statement = statement.where(EmailMessage.mail_account_id == account_id)
        if provider:
            statement = statement.where(MailAccount.provider == provider)
        if category:
            statement = statement.where(EmailAnalysis.category == category)
        if risk_level:
            statement = statement.where(EmailAnalysis.risk_level == risk_level)
        if cursor:
            timestamp, message_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    sort_time < timestamp,
                    and_(sort_time == timestamp, EmailMessage.id < message_id),
                )
            )
        rows = (
            await self.session.execute(
                statement.order_by(sort_time.desc(), EmailMessage.id.desc()).limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [
            MessageItem(
                id=row[0],
                account_id=row[1],
                provider=row[2],
                account_email=row[3],
                sender=row[4],
                subject=row[5],
                snippet=row[6],
                body=None,
                body_html=None,
                received_at=row[7],
                category=row[8],
                risk_level=row[9],
                alert_count=row[10],
                is_read=row[11],
                is_starred=row[12],
                mailbox=row[13],
                thread_id=row[14],
            )
            for row in visible
        ]
        next_cursor = (
            encode_cursor(visible[-1][15], visible[-1][0]) if has_more and visible else None
        )
        return MessagePage(items=items, next_cursor=next_cursor)

    async def alerts(
        self,
        *,
        open_only: bool,
        risk_level: RiskLevel | None,
        cursor: str | None,
        limit: int,
    ) -> AlertPage:
        statement = select(Alert).where(Alert.tenant_id == self.tenant_id)
        if open_only:
            statement = statement.where(Alert.resolved_at.is_(None))
        if risk_level:
            statement = statement.where(Alert.risk_level == risk_level)
        if cursor:
            timestamp, alert_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Alert.created_at < timestamp,
                    and_(Alert.created_at == timestamp, Alert.id < alert_id),
                )
            )
        alerts = list(
            (
                await self.session.scalars(
                    statement.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(
                        limit + 1
                    )
                )
            ).all()
        )
        has_more = len(alerts) > limit
        visible = alerts[:limit]
        return AlertPage(
            items=[
                AlertItem(
                    id=alert.id,
                    message_id=alert.email_message_id,
                    alert_type=alert.alert_type,
                    title=alert.title,
                    detail=alert.detail,
                    risk_level=alert.risk_level,
                    created_at=alert.created_at,
                    resolved_at=alert.resolved_at,
                )
                for alert in visible
            ],
            next_cursor=encode_cursor(visible[-1].created_at, visible[-1].id)
            if has_more and visible
            else None,
        )

    async def analyses(
        self,
        *,
        search: str | None,
        message_id: UUID | None,
        category: str | None,
        risk_level: RiskLevel | None,
        cursor: str | None,
        limit: int,
    ) -> AnalysisPage:
        statement = (
            select(
                EmailAnalysis,
                EmailMessage.sender,
                EmailMessage.subject,
                MailAccount.email,
            )
            .join(EmailMessage, EmailMessage.id == EmailAnalysis.email_message_id)
            .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
            .where(
                EmailAnalysis.tenant_id == self.tenant_id,
                EmailMessage.tenant_id == self.tenant_id,
                EmailMessage.deleted_at.is_(None),
            )
        )
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    EmailMessage.sender.ilike(pattern),
                    EmailMessage.subject.ilike(pattern),
                    EmailAnalysis.service.ilike(pattern),
                    EmailAnalysis.platform.ilike(pattern),
                    EmailAnalysis.category.ilike(pattern),
                )
            )
        if message_id:
            statement = statement.where(EmailAnalysis.email_message_id == message_id)
        if category:
            statement = statement.where(EmailAnalysis.category == category)
        if risk_level:
            statement = statement.where(EmailAnalysis.risk_level == risk_level)
        if cursor:
            timestamp, analysis_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    EmailAnalysis.created_at < timestamp,
                    and_(
                        EmailAnalysis.created_at == timestamp,
                        EmailAnalysis.id < analysis_id,
                    ),
                )
            )
        rows = (
            await self.session.execute(
                statement.order_by(EmailAnalysis.created_at.desc(), EmailAnalysis.id.desc())
                .limit(limit + 1)
            )
        ).all()
        has_more = len(rows) > limit
        visible = rows[:limit]
        return AnalysisPage(
            items=[
                AnalysisItem(
                    id=analysis.id,
                    message_id=analysis.email_message_id,
                    account_email=account_email,
                    sender=sender,
                    subject=subject,
                    service=analysis.service,
                    platform=analysis.platform,
                    amount=analysis.amount,
                    currency=analysis.currency,
                    country=analysis.country,
                    language=analysis.language,
                    priority=analysis.priority,
                    email_type=analysis.email_type,
                    category=analysis.category,
                    action_required=analysis.action_required,
                    risk_level=analysis.risk_level,
                    alert_types=analysis.alert_types,
                    model=analysis.model,
                    prompt_version=analysis.prompt_version,
                    created_at=analysis.created_at,
                )
                for analysis, sender, subject, account_email in visible
            ],
            next_cursor=encode_cursor(visible[-1][0].created_at, visible[-1][0].id)
            if has_more and visible
            else None,
        )

    async def active_payment_analyses(self, *, limit: int) -> AnalysisPage:
        current = (
            select(
                AnalysisIncident.current_analysis_id.label("analysis_id"),
                func.max(AnalysisIncident.last_event_received_at).label("event_at"),
            )
            .where(
                AnalysisIncident.tenant_id == self.tenant_id,
                AnalysisIncident.status == "active",
                AnalysisIncident.incident_type.in_(
                    ["payment_rejected", "payment_method_expired", "renewal_due"]
                ),
            )
            .group_by(AnalysisIncident.current_analysis_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    EmailAnalysis,
                    EmailMessage.sender,
                    EmailMessage.subject,
                    MailAccount.email,
                )
                .join(current, current.c.analysis_id == EmailAnalysis.id)
                .join(EmailMessage, EmailMessage.id == EmailAnalysis.email_message_id)
                .join(MailAccount, MailAccount.id == EmailMessage.mail_account_id)
                .where(
                    EmailAnalysis.tenant_id == self.tenant_id,
                    EmailMessage.tenant_id == self.tenant_id,
                    EmailMessage.deleted_at.is_(None),
                )
                .order_by(current.c.event_at.desc(), EmailAnalysis.id.desc())
                .limit(limit)
            )
        ).all()
        return AnalysisPage(
            items=[
                AnalysisItem(
                    id=analysis.id,
                    message_id=analysis.email_message_id,
                    account_email=account_email,
                    sender=sender,
                    subject=subject,
                    service=analysis.service,
                    platform=analysis.platform,
                    amount=analysis.amount,
                    currency=analysis.currency,
                    country=analysis.country,
                    language=analysis.language,
                    priority=analysis.priority,
                    email_type=analysis.email_type,
                    category=analysis.category,
                    action_required=analysis.action_required,
                    risk_level=analysis.risk_level,
                    alert_types=analysis.alert_types,
                    model=analysis.model,
                    prompt_version=analysis.prompt_version,
                    created_at=analysis.created_at,
                )
                for analysis, sender, subject, account_email in rows
            ],
            next_cursor=None,
        )

    async def resolve_alert(self, alert_id: UUID) -> bool:
        result = await self.session.execute(
            update(Alert)
            .where(Alert.tenant_id == self.tenant_id, Alert.id == alert_id)
            .values(resolved_at=datetime.now(UTC))
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def summary(self) -> DashboardSummary:
        now = datetime.now(UTC)
        counts = (
            await self.session.execute(
                select(
                    select(func.count(MailAccount.id))
                    .where(
                        MailAccount.tenant_id == self.tenant_id,
                        MailAccount.status == AccountStatus.CONNECTED,
                    )
                    .scalar_subquery(),
                    select(func.count(EmailMessage.id))
                    .where(EmailMessage.tenant_id == self.tenant_id)
                    .scalar_subquery(),
                    select(func.count(EmailAnalysis.id))
                    .where(EmailAnalysis.tenant_id == self.tenant_id)
                    .scalar_subquery(),
                    select(func.count(Alert.id))
                    .where(
                        Alert.tenant_id == self.tenant_id,
                        Alert.resolved_at.is_(None),
                    )
                    .scalar_subquery(),
                    select(func.count(Alert.id))
                    .where(
                        Alert.tenant_id == self.tenant_id,
                        Alert.resolved_at.is_(None),
                        Alert.risk_level == RiskLevel.CRITICAL,
                    )
                    .scalar_subquery(),
                    select(func.count(EmailMessage.id))
                    .where(
                        EmailMessage.tenant_id == self.tenant_id,
                        EmailMessage.created_at >= now - timedelta(hours=24),
                    )
                    .scalar_subquery(),
                )
            )
        ).one()
        trend_rows = (
            await self.session.execute(
                text(
                    """
                    WITH message_daily AS (
                        SELECT created_at::date AS day, count(*)::int AS messages
                        FROM email_messages
                        WHERE tenant_id = :tenant_id
                          AND created_at >= current_date - interval '13 days'
                        GROUP BY created_at::date
                    ),
                    alert_daily AS (
                        SELECT created_at::date AS day, count(*)::int AS alerts
                        FROM alerts
                        WHERE tenant_id = :tenant_id
                          AND created_at >= current_date - interval '13 days'
                        GROUP BY created_at::date
                    )
                    SELECT days.day::date,
                           coalesce(m.messages, 0)::int AS messages,
                           coalesce(a.alerts, 0)::int AS alerts
                    FROM generate_series(
                        current_date - interval '13 days',
                        current_date,
                        interval '1 day'
                    ) AS days(day)
                    LEFT JOIN message_daily m ON m.day = days.day::date
                    LEFT JOIN alert_daily a ON a.day = days.day::date
                    ORDER BY days.day
                    """
                ),
                {"tenant_id": self.tenant_id},
            )
        ).all()
        total = int(counts[1])
        analyzed = int(counts[2])
        return DashboardSummary(
            connected_accounts=int(counts[0]),
            total_messages=total,
            analyzed_messages=analyzed,
            open_alerts=int(counts[3]),
            critical_alerts=int(counts[4]),
            messages_last_24h=int(counts[5]),
            analysis_coverage_percent=round(analyzed / total * 100, 2) if total else 0,
            trend=[
                DailyMetric(day=row[0], messages=row[1], alerts=row[2])
                for row in trend_rows
            ],
        )
