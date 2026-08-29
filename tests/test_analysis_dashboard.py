from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from mail_control.modules.analysis.models import RiskLevel
from mail_control.modules.dashboard.repository import DashboardRepository
from mail_control.modules.dashboard.schemas import AnalysisItem, AnalysisPage


class EmptyResult:
    def all(self) -> list[object]:
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement: Any = None

    async def execute(self, statement: Any) -> EmptyResult:
        self.statement = statement
        return EmptyResult()


@pytest.mark.asyncio
async def test_analysis_query_is_always_scoped_to_tenant() -> None:
    tenant_id = uuid4()
    session = CapturingSession()

    page = await DashboardRepository(session, tenant_id).analyses(  # type: ignore[arg-type]
        search=None,
        message_id=None,
        category=None,
        risk_level=None,
        cursor=None,
        limit=25,
    )

    assert page == AnalysisPage(items=[], next_cursor=None)
    compiled = session.statement.compile()
    assert tenant_id in compiled.params.values()
    assert str(session.statement).count("tenant_id") >= 2


def test_analysis_item_exposes_saved_result_without_email_body() -> None:
    item = AnalysisItem(
        id=uuid4(),
        message_id=uuid4(),
        account_email="owner@example.com",
        sender="Netflix <info@example.com>",
        subject="Actualización de pago",
        service="Netflix",
        platform="Netflix",
        amount="29.90",
        currency="PEN",
        country="PE",
        language="es",
        priority="high",
        email_type="payment",
        category="Netflix",
        action_required="Revisar el método de pago.",
        risk_level=RiskLevel.HIGH,
        alert_types=["payment_rejected"],
        model="gpt-test",
        prompt_version="v1",
        created_at=datetime(2026, 8, 15, tzinfo=UTC),
    )

    payload = item.model_dump(mode="json")

    assert payload["action_required"] == "Revisar el método de pago."
    assert payload["risk_level"] == "high"
    assert "body" not in payload
    assert "body_html" not in payload
