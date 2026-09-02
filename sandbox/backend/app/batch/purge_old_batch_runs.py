# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import NotFoundError
from app.services.batch.run import BatchRunService


# ============================================================
# Constants
# ============================================================

# Ninety days keeps a quarter of history — enough to compare this month's
# failures against last month's — while the table stays thousands of rows, not
# millions. Steps go with their run: the FK is ON DELETE CASCADE.
DEFAULT_RETENTION_DAYS = 90


# ============================================================
# Functions
# ============================================================


async def purge_old_batch_runs(days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Delete runs that finished more than the given number of days ago.

    Keyed on the run's **ending**: `finished_at < cutoff` cannot match a
    `RUNNING` row, so a run in flight is unpurgeable by construction. The runs
    and steps tables otherwise grow by one run and one row per window every
    night, forever.

    Returns the number of deleted runs.
    """
    finished_before = datetime.now(UTC) - timedelta(days=days)

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin() here — transactions belong to services.
    async with AsyncSession(engine) as session:
        batch_run_service = BatchRunService(session)
        finished = await batch_run_service.find_finished_before(finished_before)
        finished_ids = [run.id for run in finished]

    # Write phase: each delete opens its own transaction via the service.
    deleted = 0
    async with AsyncSession(engine) as session:
        batch_run_service = BatchRunService(session)
        for run_id in finished_ids:
            try:
                await batch_run_service.delete_run(run_id)
                deleted += 1
            except NotFoundError:
                continue

    return deleted


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    count = asyncio.run(purge_old_batch_runs())
    print(f"Deleted {count} old batch runs")
