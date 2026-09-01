# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import NotFoundError
from app.services.refresh import RefreshService


# ============================================================
# Functions
# ============================================================

async def purge_expired_refreshes(days: int = 30) -> int:
    """Delete refresh tokens that expired more than the given number of days ago.

    The grace window is deliberate: a revoked row is what tells a replayed
    token apart from an unknown one, so tokens are kept for a while past their
    own expiry and only then dropped. Without the purge the table grows by one
    row per login forever.

    Returns the number of deleted tokens.
    """
    expired_before = datetime.now(UTC) - timedelta(days=days)

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin()/commit() here — transactions belong to
    # services and raw session usage is forbidden in batch jobs.
    async with AsyncSession(engine) as session:
        refresh_service = RefreshService(session)
        expired = await refresh_service.find_expired(expired_before)
        expired_ids = [refresh.id for refresh in expired]

    # Write phase: each delete_refresh opens its own transaction via the service.
    deleted = 0
    async with AsyncSession(engine) as session:
        refresh_service = RefreshService(session)
        for refresh_id in expired_ids:
            try:
                await refresh_service.delete_refresh(refresh_id)
                deleted += 1
            except NotFoundError:
                continue

    return deleted


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    count = asyncio.run(purge_expired_refreshes(days=30))
    print(f"Deleted {count} expired refresh tokens")
