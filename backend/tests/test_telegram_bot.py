from types import SimpleNamespace

from app import telegram_bot


def test_mask_email_keeps_domain_but_hides_local_part():
    masked = telegram_bot._mask_email("usuario@example.com")
    assert masked.startswith("us")
    assert masked.endswith("@example.com")
    assert "usuario" not in masked


def test_extract_code_prefers_contextual_code():
    message = SimpleNamespace(
        subject="Netflix: código de inicio de sesión 482913",
        snippet="",
        body_text="Este código vence pronto.",
    )
    assert telegram_bot._extract_code(message) == "482913"


def test_authorized_requires_private_admin_chat(monkeypatch):
    monkeypatch.setattr(telegram_bot.settings, "TELEGRAM_ADMIN_CHAT_ID", 123)
    assert telegram_bot._authorized(
        {"type": "private", "id": 123},
        {"id": 123},
    )
    assert not telegram_bot._authorized(
        {"type": "group", "id": 123},
        {"id": 123},
    )
    assert not telegram_bot._authorized(
        {"type": "private", "id": 123},
        {"id": 999},
    )
