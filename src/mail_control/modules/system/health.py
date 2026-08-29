from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from mail_control.infrastructure.resources import Resources


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    database: bool
    redis: bool
    rabbitmq: bool

    @property
    def ready(self) -> bool:
        return self.database and self.redis and self.rabbitmq


async def check_dependencies(resources: Resources) -> DependencyStatus:
    database_ok = redis_ok = rabbitmq_ok = False

    try:
        async with resources.database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False

    try:
        redis_ok = bool(await resources.redis.ping())
    except Exception:
        redis_ok = False

    rabbitmq_ok = not resources.rabbitmq.is_closed
    return DependencyStatus(database_ok, redis_ok, rabbitmq_ok)
