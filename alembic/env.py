from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from mail_control.infrastructure.database.base import Base
from mail_control.modules.analysis import models as analysis_models
from mail_control.modules.identity import models as identity_models
from mail_control.modules.mail import models as mail_models
from mail_control.modules.saas import models as saas_models
from mail_control.settings import get_settings

_ = identity_models
_ = mail_models
_ = analysis_models
_ = saas_models
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = get_settings()
# Runtime traffic uses the restricted application role and global jobs may use
# a BYPASSRLS role.  DDL needs the table owner, so deployments can provide an
# explicit, dedicated connection without broadening either runtime role.
migration_database_url = (
    settings.migration_database_url
    or settings.system_database_url
    or settings.database_url
)
config.set_main_option("sqlalchemy.url", migration_database_url)
target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    context.configure(
        url=migration_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
