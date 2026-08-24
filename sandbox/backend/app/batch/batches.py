# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import NotFoundError
from app.services.batch import BatchService


# ============================================================
# Functions
# ============================================================

async def purge_stale_batches(days: int = 30) -> int:
    """Delete batches older than the given number of days.

    Uses BatchService.delete_batch to reuse existing deletion logic.
    Returns the number of deleted batches.
    """
    older_than = datetime.now(UTC) - timedelta(days=days)

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin()/commit() here — transactions belong to
    # services and raw session usage is forbidden in batch jobs.
    async with AsyncSession(engine) as session:
        batch_service = BatchService(session)
        stale_batches = await batch_service.find_stale(older_than)
        stale_ids = [batch.id for batch in stale_batches]

    # Write phase: each delete_batch opens its own transaction via the service.
    deleted = 0
    async with AsyncSession(engine) as session:
        batch_service = BatchService(session)
        for batch_id in stale_ids:
            try:
                await batch_service.delete_batch(batch_id)
                deleted += 1
            except NotFoundError:
                continue

    return deleted


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    count = asyncio.run(purge_stale_batches(days=30))
    print(f"Deleted {count} stale batches")
