from __future__ import annotations

from dataclasses import dataclass

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from redis.asyncio import Redis

from mail_control.infrastructure.database.session import Database
from mail_control.settings import Settings


@dataclass(slots=True)
class Resources:
    database: Database
    system_database: Database
    redis: Redis
    rabbitmq: AbstractRobustConnection

    @classmethod
    async def connect(cls, settings: Settings) -> Resources:
        if settings.is_production and not settings.system_database_url:
            raise RuntimeError("SYSTEM_DATABASE_URL is required in production")
        database = Database(settings.database_url)
        system_database = (
            Database(settings.system_database_url)
            if settings.system_database_url
            else database
        )
        if settings.is_production:
            runtime_superuser, runtime_bypass = await database.role_security_attributes()
            if runtime_superuser or runtime_bypass:
                await database.close()
                if system_database is not database:
                    await system_database.close()
                raise RuntimeError(
                    "DATABASE_URL must use a NOSUPERUSER NOBYPASSRLS role"
                )
            system_superuser, system_bypass = (
                await system_database.role_security_attributes()
            )
            if not (system_superuser or system_bypass):
                await database.close()
                await system_database.close()
                raise RuntimeError(
                    "SYSTEM_DATABASE_URL must use a role allowed to run global jobs"
                )
        return cls(
            database=database,
            system_database=system_database,
            redis=Redis.from_url(settings.redis_url, decode_responses=True),
            rabbitmq=await aio_pika.connect_robust(settings.rabbitmq_url),
        )

    async def close(self) -> None:
        await self.rabbitmq.close()
        await self.redis.aclose()
        await self.database.close()
        if self.system_database is not self.database:
            await self.system_database.close()
