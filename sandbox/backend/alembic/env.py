import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.settings import settings
from app.models.base import Base
from app.models.batch import Batch  # noqa: F401 — on metadata
from app.models.integration.call import IntegrationCall  # noqa: F401 — on metadata
from app.models.integration.field import IntegrationField  # noqa: F401 — on metadata
from app.models.integration.operation import IntegrationOperation  # noqa: F401 — on metadata
from app.models.integration.provider import Integration  # noqa: F401 — on metadata
from app.models.integration.secret import IntegrationSecret  # noqa: F401 — on metadata
from app.models.refresh import Refresh  # noqa: F401 — on metadata
from app.models.user import User  # noqa: F401 — on metadata


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
    # One transaction per migration, not one for the whole run. A multi-step run
    # that fails then stops at the last revision that fully applied, so the
    # version pointer and the rows still agree.
    #
    # Measured the other way round: a `downgrade base` that failed part-way left a
    # database whose pointer said 65 while an operation row from revision 66 was
    # still there, and the next `upgrade head` died on
    # `uq_integration_operation_provider_code`. Half an hour then went into
    # diagnosing a migration ordering defect that does not exist - the chain
    # downgrades cleanly from a consistent database.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
