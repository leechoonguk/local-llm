# ============================================================
# Imports
# ============================================================

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.cache import RedisCache
from app.core.database import engine
from app.core.scheduler import BatchScheduler


# ============================================================
# Constants
# ============================================================

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ============================================================
# Functions
# ============================================================

async def get_session() -> AsyncIterator[AsyncSession]:
    """Inject an AsyncSession for the request lifecycle.

    Transaction commit/rollback is managed explicitly in service layers
    via `session.commit()` / `session.rollback()`.
    """
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()


# ============================================================
# Dependencies
# ============================================================

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_cache(request: Request) -> RedisCache | None:
    return request.app.state.redis_cache


CacheDep = Annotated[RedisCache | None, Depends(get_cache)]


async def get_scheduler(request: Request) -> BatchScheduler | None:
    """The running scheduler, or None where none runs (tests, worker-less runs)."""
    return request.app.state.scheduler


SchedulerDep = Annotated[BatchScheduler | None, Depends(get_scheduler)]
