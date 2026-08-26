import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.settings import settings
from app.models.base import Base
from app.models.batch import Batch  # noqa: F401 — register model on metadata
from app.models.integration import (
    Integration,  # noqa: F401 — register model on metadata
    IntegrationField,  # noqa: F401 — register model on metadata
    IntegrationOperation,  # noqa: F401 — register model on metadata
    IntegrationSecret,  # noqa: F401 — register model on metadata
)
from app.models.notice import Notice  # noqa: F401 — register model on metadata


config = context.config

# Use DATABASE_URL from Settings/env, not alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async def _run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(_run())


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
