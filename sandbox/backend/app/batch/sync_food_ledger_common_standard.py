# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio

from app.core.ledger import Feed
from app.services.batch.ledger_feed import sync_ledger
from app.services.food.ledger_common_standard import FoodLedgerCommonStandardService


# ============================================================
# Constants
# ============================================================

# The provider this job reads, by the code the seeds wrote. A job names an
# operation, never a URL: the path, the key, the filters and the paging family
# all live in `integration_field`.
PROVIDER_CODE = "mfds-food-safety-korea"

# Every service of this portal caps one call at 1000 rows (`ERROR-336`), and
# the cap is the width: a narrower window costs the same latency per call.
PAGE_SIZE = 1000

# What this portal answers past its last row: `INFO-200 해당하는 데이터가
# 없습니다`. Some operations list it among their envelope values and the walk
# sees an empty page; the rest refuse with it, and both are the end of the feed.
END_CODES: frozenset[str] = frozenset({"INFO-200"})

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_food_ledger_common_standard"

# The one feed this job walks, and the one ledger it fills.
FEED = Feed(
    "search-common-standard",
    FoodLedgerCommonStandardService,
    FoodLedgerCommonStandardService.replace_common_standard_ledger,
)


# ============================================================
# Functions
# ============================================================


async def sync_food_ledger_common_standard() -> int:
    """Replace this ledger with a whole pass of its 식품안전나라 feed.

    The ledger is `food_ledger_common_standard`.
    The feed is `search-common-standard`.

    One job, one ledger: this walk has its own schedule row, its own run and
    its own steps, and no other ledger waits behind it. Windows of
    `PAGE_SIZE` rows from the first until one comes back short; no cursor and
    no `total_count`, so the ledger after a pass *is* the pass.

    Measured: 57,457 rows, 729 windows at 10.4 s - 2 h 06 m, the longest walk of this provider
    (2026-09-15).

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
    total = asyncio.run(sync_food_ledger_common_standard())
    print(f"Changed {total} ledger rows")
