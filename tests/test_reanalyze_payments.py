from uuid import uuid4

from mail_control.modules.analysis.models import EmailAnalysis, RiskLevel
from mail_control.scripts.reanalyze_payments import is_payment_analysis


def analysis_with(alert_types: list[str]) -> EmailAnalysis:
    return EmailAnalysis(
        id=uuid4(),
        tenant_id=uuid4(),
        email_message_id=uuid4(),
        language="es",
        priority="media",
        email_type="payment",
        category="Pagos",
        risk_level=RiskLevel.MEDIUM,
        alert_types=alert_types,
        model="test",
        prompt_version="legacy",
    )


def test_payment_analysis_is_selected() -> None:
    assert is_payment_analysis(analysis_with(["payment_rejected"]))
    assert is_payment_analysis(analysis_with(["renewal_due", "security"]))


def test_security_analysis_is_not_selected() -> None:
    assert not is_payment_analysis(analysis_with(["security", "access_attempt"]))
