from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services import telegram_notifier
from app.workers import tasks


def test_telegram_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_ADMIN_CHAT_ID", 0)
    assert telegram_notifier.enabled() is False
    assert telegram_notifier.send_message("prueba") is False


def test_notification_failure_does_not_escape(monkeypatch):
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_ADMIN_CHAT_ID", 123)

    def fail(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(telegram_notifier, "_call", fail)
    assert telegram_notifier.send_message("prueba") is False


def test_daily_summary_combines_enterprise_and_legacy_without_duplicates(monkeypatch):
    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(email="shared@example.com", last_status="ok"),
        SimpleNamespace(email="legacy@example.com", last_status="ok"),
    ]
    db.scalar.side_effect = [4, 5]
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(tasks.settings, "TELEGRAM_DAILY_SUMMARY", True)
    monkeypatch.setattr(tasks.enterprise_bridge, "accounts", lambda: [
        {"email": "shared@example.com", "status": "CONNECTED"},
        {"email": "enterprise@example.com", "status": "ERROR"},
    ])
    monkeypatch.setattr(tasks.enterprise_bridge, "message_count_since", lambda since: 7)
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(tasks.telegram_notifier, "send_message", sent)

    assert tasks.send_telegram_daily_summary.run() == 1

    text = sent.call_args.args[0]
    assert "Cuentas: <b>3</b>" in text
    assert "Conectadas: <b>2</b>" in text
    assert "Con error: <b>1</b>" in text
    assert "Alertas pendientes: <b>4</b>" in text
    assert "Correos recibidos en 24 h: <b>12</b>" in text
