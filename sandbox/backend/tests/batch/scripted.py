"""A scripted provider walk for the ledger job tests.

The jobs talk to the provider through `IntegrationOperationService.walk_operation`
and nothing else; scripting that seam leaves the job's own contract under
test - which feeds it walks, in what order, what it writes, what it records
and how one feed's failure reaches the run - without seeding an operation's
fields for a request nobody sends.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.integration import IntegrationPage, paging_window
from app.models.base import Base
from app.models.batch.step import BatchStep
from app.services.batch.run import BatchRunService, current_run_id
from app.services.integration.operation import IntegrationOperationService


@asynccontextmanager
async def swapped_engine(module) -> AsyncIterator[AsyncEngine]:
    """In-memory engine + tables, standing in for the job module's `engine`."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    original = module.engine
    module.engine = engine
    try:
        yield engine
    finally:
        module.engine = original
        await engine.dispose()


def script_walk(
    monkeypatch: pytest.MonkeyPatch,
    family: str,
    feeds: Mapping[str, Sequence[Sequence[object] | Exception]],
) -> list[tuple[str, dict[str, int]]]:
    """Answer each feed's walk with its scripted pages; record every window asked.

    A feed's script is its pages in order; an exception in the sequence is
    raised where it stands, the way a refusal arrives mid-walk. The walk ends
    where the real one does - at the first page shorter than the window.
    """
    asked: list[tuple[str, dict[str, int]]] = []

    async def _walk(self, provider_code, operation_code, *, actor, page_size, end_codes):
        for index, answer in enumerate(feeds[operation_code]):
            window = paging_window(family, index, page_size)
            asked.append((operation_code, window))
            if isinstance(answer, Exception):
                raise answer
            yield IntegrationPage(window=window, records=list(answer), call_id=None, duration_ms=1)
            if len(answer) < page_size:
                return

    monkeypatch.setattr(IntegrationOperationService, "walk_operation", _walk)
    return asked


async def run_in_context(engine: AsyncEngine, job_code: str) -> UUID:
    """Open a run and put it in context, the way the scheduler does."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        run = await BatchRunService(session).create_started_run(None, job_code, "CRON", "scheduler")
    current_run_id.set(run.id)
    return run.id


async def steps(engine: AsyncEngine) -> list[BatchStep]:
    """Every step of every run, in sequence order."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return list(
            (await session.execute(select(BatchStep).order_by(BatchStep.sequence))).scalars().all()
        )


async def rows(engine: AsyncEngine, model) -> list:
    """The ledger as a separate session sees it."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return list((await session.execute(select(model))).scalars().all())
