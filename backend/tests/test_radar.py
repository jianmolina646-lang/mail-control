from app.services.radar import classify


def test_rejects_sender_that_only_contains_service_name():
    result = classify(
        "Netflix Security <support@netflix-security.example>",
        "Payment failed",
        "Update your card.",
    )
    assert result.service == ""
    assert result.status == "unknown"
    assert result.sender_trusted is False
    assert "no es oficial" in result.security_warning


def test_detects_payment_failure_from_trusted_domain():
    result = classify(
        "Netflix <info@mailer.netflix.com>",
        "Payment failed for your membership",
        "",
    )
    assert result.service == "Netflix"
    assert result.status == "payment_failed"
    assert result.severity == "critical"
    assert result.is_alert is True


def test_welcome_message_is_not_alerted_by_generic_payment_word():
    result = classify(
        "Netflix <info@netflix.com>",
        "Welcome to Netflix",
        "Your payment information is available in your account.",
    )
    assert result.service == "Netflix"
    assert result.status == "unknown"
    assert result.is_alert is False


def test_recovery_message_marks_subscription_active():
    result = classify(
        "Prime Video <notice@amazon.com>",
        "Payment successful",
        "Your Prime membership is active.",
    )
    assert result.service == "Prime Video"
    assert result.status == "active"
    assert result.is_alert is False


def test_recovery_subject_wins_over_old_failure_text_in_body():
    result = classify(
        "Netflix <info@netflix.com>",
        "Payment successful",
        "Previously your payment failed. Your membership has been reactivated.",
    )
    assert result.status == "active"
    assert result.is_alert is False


def test_normal_unknown_sender_is_not_flagged_as_impersonation():
    result = classify(
        "Customer <customer@example.com>",
        "Question about an order",
        "",
    )
    assert result.sender_trusted is True
    assert result.security_warning == ""


def test_regular_amazon_purchase_is_not_prime_subscription():
    result = classify(
        "Amazon <shipment@amazon.com>",
        "Payment successful for your order",
        "Your package will arrive tomorrow.",
    )
    assert result.service == ""
    assert result.status == "unknown"


def test_warning_is_separate_from_critical_failure():
    result = classify(
        "Disney+ <billing@disneyplus.com>",
        "Please update your payment method",
        "",
    )
    assert result.status == "warning"
    assert result.severity == "warning"
