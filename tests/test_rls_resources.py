from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mail_control.infrastructure import resources as resources_module
from mail_control.infrastructure.resources import Resources
from mail_control.settings import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "app_secret_key": "x" * 32,
        "database_url": "postgresql+asyncpg://runtime/db",
        "system_database_url": "postgresql+asyncpg://system/db",
        "redis_url": "redis://redis/0",
        "rabbitmq_url": "amqp://rabbitmq/",
    }
    values.update(overrides)
    return Settings(**values)


async def test_production_requires_separate_system_database_url() -> None:
    with pytest.raises(RuntimeError, match="SYSTEM_DATABASE_URL"):
        await Resources.connect(production_settings(system_database_url=None))


async def test_production_rejects_rls_bypass_runtime_role(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        instances: list[FakeDatabase] = []

        def __init__(self, url: str) -> None:
            self.url = url
            self.closed = False
            self.instances.append(self)

        async def role_security_attributes(self) -> tuple[bool, bool]:
            return (False, self.url.endswith("runtime/db"))

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(resources_module, "Database", FakeDatabase)

    with pytest.raises(RuntimeError, match="NOSUPERUSER NOBYPASSRLS"):
        await Resources.connect(production_settings())

    assert len(FakeDatabase.instances) == 2
    assert all(database.closed for database in FakeDatabase.instances)


async def test_production_accepts_restricted_runtime_and_privileged_system_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDatabase:
        def __init__(self, url: str) -> None:
            self.url = url

        async def role_security_attributes(self) -> tuple[bool, bool]:
            return (False, self.url.endswith("system/db"))

        async def close(self) -> None:
            return None

    rabbitmq = AsyncMock()
    monkeypatch.setattr(resources_module, "Database", FakeDatabase)
    monkeypatch.setattr(resources_module.aio_pika, "connect_robust", rabbitmq)

    resources = await Resources.connect(production_settings())

    assert resources.database.url.endswith("runtime/db")
    assert resources.system_database.url.endswith("system/db")
    rabbitmq.assert_awaited_once()
