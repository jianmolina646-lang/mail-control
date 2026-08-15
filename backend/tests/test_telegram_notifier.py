from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services import telegram_notifier
from app.workers import tasks


def test_telegram_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(telegram_notifier.settings, "BACKUP_TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(telegram_notifier.settings, "BACKUP_TELEGRAM_CHAT_ID", 0)
    assert telegram_notifier.enabled() is False
    assert telegram_notifier.send_message("prueba") is False


def test_notification_failure_does_not_escape(monkeypatch):
    monkeypatch.setattr(telegram_notifier.settings, "BACKUP_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(telegram_notifier.settings, "BACKUP_TELEGRAM_CHAT_ID", 123)

    def fail(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(telegram_notifier, "_call", fail)
    assert telegram_notifier.send_message("prueba") is False


def test_notifications_use_infrastructure_bot(monkeypatch):
    monkeypatch.setattr(
        telegram_notifier.settings,
        "BACKUP_TELEGRAM_BOT_TOKEN",
        "infra-token",
    )
    monkeypatch.setattr(telegram_notifier.settings, "BACKUP_TELEGRAM_CHAT_ID", 456)
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_BOT_TOKEN", "mail-token")
    monkeypatch.setattr(telegram_notifier.settings, "TELEGRAM_ADMIN_CHAT_ID", 123)
    urlopen = MagicMock()
    response = MagicMock()
    response.read.return_value = b'{"ok": true}'
    urlopen.return_value.__enter__.return_value = response
    monkeypatch.setattr(telegram_notifier.request, "urlopen", urlopen)

    assert telegram_notifier.send_message("prueba") is True

    request = urlopen.call_args.args[0]
    assert "infra-token" in request.full_url
    assert "mail-token" not in request.full_url
    assert b"chat_id=456" in request.data
    assert b"chat_id=123" not in request.data


def test_sent_message_id_is_remembered(monkeypatch):
    pipeline = MagicMock()
    monkeypatch.setattr(telegram_notifier._redis, "pipeline", lambda: pipeline)
    telegram_notifier._remember_message({
        "ok": True,
        "result": {"message_id": 88, "chat": {"id": 456}},
    })
    pipeline.lpush.assert_called_once()
    stored = pipeline.lpush.call_args.args[1]
    assert '"chat_id": "456"' in stored
    assert '"message_id": 88' in stored
    pipeline.ltrim.assert_called_once_with(
        telegram_notifier._SENT_MESSAGES_KEY,
        0,
        999,
    )
    pipeline.execute.assert_called_once()


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
