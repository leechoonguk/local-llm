# ============================================================
# Imports
# ============================================================

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import settings


if settings.database_url.startswith("postgresql+asyncpg://"):
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True,
    )
else:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
