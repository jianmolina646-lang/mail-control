from datetime import UTC, datetime, timedelta

from mail_control.modules.identity.service import (
    session_absolute_deadline,
    session_refresh_deadline,
)
from mail_control.settings import Settings


def settings() -> Settings:
    return Settings(
        app_secret_key="x" * 32,
        database_url="postgresql+asyncpg://example",
        redis_url="redis://example",
        rabbitmq_url="amqp://example",
        session_idle_minutes=30,
        session_absolute_hours=12,
    )


def test_refresh_deadline_uses_idle_timeout() -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)

    deadline = session_refresh_deadline(
        settings(),
        now=now,
        started_at=now - timedelta(hours=1),
    )

    assert deadline == now + timedelta(minutes=30)


def test_refresh_deadline_never_exceeds_absolute_timeout() -> None:
    started_at = datetime(2026, 8, 15, 1, tzinfo=UTC)
    now = started_at + timedelta(hours=11, minutes=50)

    deadline = session_refresh_deadline(
        settings(),
        now=now,
        started_at=started_at,
    )

    assert deadline == session_absolute_deadline(settings(), started_at)
