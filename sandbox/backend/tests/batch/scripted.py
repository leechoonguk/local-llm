"""A scripted provider walk for the ledger job tests.

The jobs talk to the provider through `IntegrationOperationService.walk_operation`
and nothing else; scripting that seam leaves the job's own contract under
test - which feeds it walks, in what order, what it writes, what it records
and how one feed's failure reaches the run - without seeding an operation's
fields for a request nobody sends.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any
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

from app.core.integration import IntegrationExecutionResult, IntegrationPage, paging_window
from app.models.base import Base
from app.models.batch.step import BatchStep
from app.services.batch.run import BatchRunService, current_run_id
from app.services.integration.operation import IntegrationOperationService
from tests.conftest import with_postgresql_functions


@asynccontextmanager
async def swapped_engine(module) -> AsyncIterator[AsyncEngine]:
    """In-memory engine + tables, standing in for the job module's `engine`."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with_postgresql_functions(engine)
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
    feeds: Mapping[str, Any],
    page_size: int = 100,
    segmentation: tuple[str, list[str]] | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """Answer each feed's walk with its scripted pages; record every window asked.

    A feed's script is its pages in order; an exception in the sequence is
    raised where it stands, the way a refusal arrives mid-walk. The walk ends
    where the real one does - at the first page shorter than the window.

    The width is the script's, standing in for the operation's own `page_size`:
    the real walk reads it off the configuration, so a job never states one
    (rule://backend-ledger).

    `segmentation` stands in for the operation's `segment_key` /
    `segment_values` the same way. It is configuration, not a job's fact, so
    a test says it here rather than reaching into a `Feed`.
    """
    asked: list[tuple[str, dict[str, object]]] = []

    async def _segmentation(self, provider_code, operation_code):
        return segmentation

    monkeypatch.setattr(IntegrationOperationService, "segmentation_of", _segmentation)

    async def _walk(self, provider_code, operation_code, *, actor, end_codes, segment=None):
        script = feeds[operation_code]
        if segment:
            # A segmented feed's script is keyed by the segment's value: the
            # walk is one run of positions per value, and the test says what
            # each value answers.
            script = script[next(iter(segment.values()))]
        for index, answer in enumerate(script):
            window: dict[str, object] = dict(paging_window(family, index, page_size))
            window.update(segment or {})
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


def script_segments(
    monkeypatch: pytest.MonkeyPatch,
    counts: Mapping[str, Mapping[str, int]],
) -> None:
    """Answer the segment discovery: how many rows each candidate value holds.

    A segmented feed asks the provider for one row of each candidate value and
    reads `total_count`; a value nothing answers for is not walked. The job
    asks for years it may not know about yet, so a value missing here is zero.
    """

    async def _execute(self, provider_code, operation_code, inputs, *, actor, client=None):
        value = str(inputs.get("report_year"))
        total = counts.get(operation_code, {}).get(value, 0)
        result = IntegrationExecutionResult(
            canonical_payload=[],
            metadata={"total_count": str(total)},
            status_code=200,
        )
        return result, None

    monkeypatch.setattr(IntegrationOperationService, "execute_operation", _execute)
