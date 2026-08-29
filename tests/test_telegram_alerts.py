from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from mail_control.modules.mail.models import AccountStatus, MailAccount, MailProvider
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from mail_control.settings import Settings


class FakeRedis:
    def __init__(self) -> None:
        self.values: set[str] = set()

    async def set(self, key: str, value: str, **kwargs: object) -> bool:
        if key in self.values:
            return False
        self.values.add(key)
        return True

    async def getdel(self, key: str) -> str | None:
        if key not in self.values:
            return None
        self.values.remove(key)
        return "1"

    async def delete(self, key: str) -> int:
        if key not in self.values:
            return 0
        self.values.remove(key)
        return 1


def account() -> MailAccount:
    return MailAccount(
        id=uuid4(), tenant_id=uuid4(), connected_by_user_id=uuid4(),
        provider=MailProvider.GMAIL, provider_account_id="owner@example.com",
        email="owner@example.com", encrypted_refresh_token="encrypted",
        status=AccountStatus.CONNECTED,
    )


def settings(secret_file: str) -> Settings:
    return Settings(
        app_secret_key="x" * 32,
        database_url="postgresql+asyncpg://example",
        redis_url="redis://example",
        rabbitmq_url="amqp://example",
        telegram_alerts_file=secret_file,
    )


@pytest.mark.asyncio
async def test_issue_is_deduplicated_and_recovery_is_sent(tmp_path: Path) -> None:
    path = tmp_path / "telegram.env"
    path.write_text("TELEGRAM_BOT_TOKEN=token\nTELEGRAM_CHAT_ID=chat\n", encoding="utf-8")
    alerts = TelegramAlerts(settings(str(path)), cast(Redis, FakeRedis()))
    sent: list[str] = []

    async def send(message: str) -> bool:
        sent.append(message)
        return True

    alerts._send = send  # type: ignore[method-assign]
    mail_account = account()
    await alerts.account_issue(mail_account, "expired")
    await alerts.account_issue(mail_account, "expired again")
    await alerts.account_recovered(mail_account)

    assert len(sent) == 2
    assert "requiere atención" in sent[0]
    assert "recuperada" in sent[1]
