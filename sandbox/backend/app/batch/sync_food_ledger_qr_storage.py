# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio

from app.core.ledger import Feed
from app.services.batch.ledger_feed import sync_ledger
from app.services.food.ledger_qr_storage import FoodLedgerQrStorageService


# ============================================================
# Constants
# ============================================================

# The provider this job reads, by the code the seeds wrote. A job names an
# operation, never a URL: the path, the key, the filters and the paging family
# all live in `integration_field`.
PROVIDER_CODE = "data-go-kr"

# The width this feed is walked at, which is its own
# `integration_operation.page_size`: this gateway's narrowest service answers
# 100 and its widest 500, and one width for both cost 13 hours against 66
# minutes on the largest feed (2026-09-14).
PAGE_SIZE = 100

# The gateway has no envelope code for "no rows": a window past the last record
# is an empty page, which is the walk's own end rule.
END_CODES: frozenset[str] = frozenset()

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_food_ledger_qr_storage"

# The one feed this job walks, and the one ledger it fills.
FEED = Feed(
    "search-food-qr-storage",
    FoodLedgerQrStorageService,
    FoodLedgerQrStorageService.replace_qr_storage_ledger,
)


# ============================================================
# Functions
# ============================================================


async def sync_food_ledger_qr_storage() -> int:
    """Replace this ledger with a whole pass of its data.go.kr feed.

    The ledger is `food_ledger_qr_storage`.
    The feed is `search-food-qr-storage`.

    One job, one ledger: this walk has its own schedule row, its own run and
    its own steps, and no other ledger waits behind it. Windows of
    `PAGE_SIZE` rows from the first until one comes back short; no cursor and
    no `total_count`, so the ledger after a pass *is* the pass.

    Measured: 2,868 rows (2026-09-13).

    Returns the rows the pass wrote.
    """
    return await sync_ledger(
        PROVIDER_CODE,
        FEED,
        SYNCED_BY,
        page_size=PAGE_SIZE,
        end_codes=END_CODES,
    )


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    total = asyncio.run(sync_food_ledger_qr_storage())
    print(f"Changed {total} ledger rows")
