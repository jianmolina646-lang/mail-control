from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import every mapped model before a worker flushes an ORM entity. Workers do not
# load the FastAPI routers, so relying on router imports leaves foreign-key
# targets such as ``users`` absent from SQLAlchemy's metadata.
from mail_control.modules.analysis import models as analysis_models  # noqa: F401,E402
from mail_control.modules.identity import models as identity_models  # noqa: F401,E402
from mail_control.modules.mail import models as mail_models  # noqa: F401,E402
from mail_control.modules.saas import models as saas_models  # noqa: F401,E402


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def role_security_attributes(self) -> tuple[bool, bool]:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT rolsuper, rolbypassrls "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                )
            ).one()
        return bool(row.rolsuper), bool(row.rolbypassrls)

    async def close(self) -> None:
        await self.engine.dispose()
