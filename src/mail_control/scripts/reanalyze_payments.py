from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import Text, cast, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.database.session import Database
from mail_control.modules.analysis.client import PROMPT_VERSION
from mail_control.modules.analysis.models import Alert, AlertType, EmailAnalysis
from mail_control.modules.analysis.openai import OpenAIClient
from mail_control.modules.analysis.schemas import AnalysisResult
from mail_control.modules.analysis.service import (
    analysis_input,
    suppress_confirmed_payment_alerts,
)
from mail_control.modules.mail.models import EmailMessage
from mail_control.settings import get_settings

PAYMENT_ALERTS = frozenset(
    {
        AlertType.PAYMENT_REJECTED.value,
        AlertType.PAYMENT_METHOD_EXPIRED.value,
        AlertType.RENEWAL_DUE.value,
    }
)


@dataclass(slots=True)
class RunSummary:
    candidates: int = 0
    processed: int = 0
    changed: int = 0
    unchanged: int = 0
    failed: int = 0


def is_payment_analysis(analysis: EmailAnalysis) -> bool:
    return bool(PAYMENT_ALERTS.intersection(analysis.alert_types))


def result_changed(analysis: EmailAnalysis, result: AnalysisResult) -> bool:
    return any(
        (
            analysis.service != result.service,
            analysis.platform != result.platform,
            analysis.amount != result.amount,
            analysis.currency != result.currency,
            analysis.country != result.country,
            analysis.language != result.language,
            analysis.priority != result.priority,
            analysis.email_type != result.email_type,
            analysis.category != result.category.value,
            analysis.action_required != result.action_required,
            analysis.risk_level != result.risk_level,
            analysis.alert_types != [item.value for item in result.alert_types],
        )
    )


def stored_result(analysis: EmailAnalysis) -> AnalysisResult:
    return AnalysisResult.model_validate(
        {
            "service": analysis.service,
            "platform": analysis.platform,
            "amount": analysis.amount,
            "currency": analysis.currency,
            "country": analysis.country,
            "language": analysis.language,
            "priority": analysis.priority,
            "email_type": analysis.email_type,
            "category": analysis.category,
            "action_required": analysis.action_required,
            "risk_level": analysis.risk_level,
            "alert_types": analysis.alert_types,
        }
    )


async def apply_result(
    session: AsyncSession,
    analysis: EmailAnalysis,
    result: AnalysisResult,
    model: str,
) -> None:
    analysis.service = result.service
    analysis.platform = result.platform
    analysis.amount = result.amount
    analysis.currency = result.currency
    analysis.country = result.country
    analysis.language = result.language
    analysis.priority = result.priority
    analysis.email_type = result.email_type
    analysis.category = result.category.value
    analysis.action_required = result.action_required
    analysis.risk_level = result.risk_level
    analysis.alert_types = [item.value for item in result.alert_types]
    analysis.model = model
    analysis.prompt_version = PROMPT_VERSION
    await session.execute(delete(Alert).where(Alert.analysis_id == analysis.id))
    for alert_type in result.alert_types:
        session.add(
            Alert(
                tenant_id=analysis.tenant_id,
                email_message_id=analysis.email_message_id,
                analysis_id=analysis.id,
                alert_type=alert_type,
                title=f"{result.category.value}: {alert_type.value}",
                detail=result.action_required,
                risk_level=result.risk_level,
            )
        )


async def run(
    *,
    apply: bool,
    limit: int | None,
    suppress_confirmed: bool = False,
) -> RunSummary:
    settings = get_settings()
    if (
        not suppress_confirmed
        and (settings.ai_provider != "openai" or not settings.openai_api_key)
    ):
        raise RuntimeError("OpenAI must be configured for payment reanalysis")
    database = Database(settings.system_database_url or settings.database_url)
    client = (
        None
        if suppress_confirmed
        else OpenAIClient(str(settings.openai_api_key), settings.openai_model)
    )
    summary = RunSummary()
    try:
        async for session in database.session():
            payment_pattern = or_(*(
                cast(EmailAnalysis.alert_types, Text).like(f'%"{alert_type}"%')
                for alert_type in PAYMENT_ALERTS
            ))
            statement = select(EmailAnalysis.id).where(payment_pattern)
            if not suppress_confirmed:
                statement = statement.where(
                    EmailAnalysis.prompt_version != PROMPT_VERSION
                )
            statement = statement.order_by(EmailAnalysis.created_at)
            if limit is not None:
                statement = statement.limit(limit)
            analysis_ids = list((await session.scalars(statement)).all())
            summary.candidates = len(analysis_ids)
            if not apply and not suppress_confirmed:
                return summary
            for analysis_id in analysis_ids:
                try:
                    async with database.session_factory() as item_session:
                        row = (
                            await item_session.execute(
                                select(EmailAnalysis, EmailMessage)
                                .join(
                                    EmailMessage,
                                    EmailMessage.id == EmailAnalysis.email_message_id,
                                )
                                .where(EmailAnalysis.id == analysis_id)
                            )
                        ).one()
                        analysis, message = row
                        email_data = analysis_input(message)
                        if suppress_confirmed:
                            result = stored_result(analysis)
                            suppressed = suppress_confirmed_payment_alerts(
                                result,
                                email_data,
                            )
                            if not suppressed:
                                summary.processed += 1
                                summary.unchanged += 1
                                continue
                        else:
                            assert client is not None
                            result = await client.analyze(email_data)
                            suppress_confirmed_payment_alerts(result, email_data)
                        changed = result_changed(analysis, result)
                        if apply:
                            model = analysis.model if client is None else client.model
                            await apply_result(item_session, analysis, result, model)
                            await item_session.commit()
                    summary.processed += 1
                    if changed:
                        summary.changed += 1
                    else:
                        summary.unchanged += 1
                except Exception as error:
                    summary.failed += 1
                    reason = str(error).replace("\n", " ")[:160]
                    print(
                        "REANALYZE_PAYMENT_FAILURE "
                        f"type={type(error).__name__} reason={reason}"
                    )
            return summary
    finally:
        await database.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Reanalyze legacy payment alerts")
    parser.add_argument("--apply", action="store_true", help="Persist valid results")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--suppress-confirmed",
        action="store_true",
        help="Remove payment alerts from confirmed successful updates without OpenAI",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be greater than zero")
    summary = asyncio.run(
        run(
            apply=args.apply,
            limit=args.limit,
            suppress_confirmed=args.suppress_confirmed,
        )
    )
    mode = "APPLY" if args.apply else "DRY_RUN"
    print(
        f"REANALYZE_PAYMENTS_{mode} candidates={summary.candidates} "
        f"processed={summary.processed} changed={summary.changed} "
        f"unchanged={summary.unchanged} failed={summary.failed}"
    )


if __name__ == "__main__":
    main()
