from app.services import telegram_notifier


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
