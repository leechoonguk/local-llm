# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio

from app.core.ledger import Feed
from app.services.batch.ledger_feed import sync_ledger
from app.services.food.ledger_additive_manufacturing_closure import (
    FoodLedgerAdditiveManufacturingClosureService,
)


# ============================================================
# Constants
# ============================================================

# The provider this job reads, by the code the seeds wrote. A job names an
# operation, never a URL: the path, the key and the file door all live in
# `integration_field`.
PROVIDER_CODE = "mfds-food-safety-korea"

# Rows per chunk the file stream hands the stage - the width every file feed
# of this portal is staged at, so a step reads as 1,000 rows.
PAGE_SIZE = 1000

# What this portal answers past its last row on a paged walk. A file has no
# window and ends when the bytes do, but the constant is the provider's, and
# every job of the provider states it.
END_CODES: frozenset[str] = frozenset({"INFO-200"})

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:sync_food_ledger_additive_manufacturing_closure"

# The one feed this job walks, and the one ledger it fills.
FEED = Feed(
    "search-food-additive-manufacturing-closure",
    FoodLedgerAdditiveManufacturingClosureService,
    FoodLedgerAdditiveManufacturingClosureService.replace_additive_manufacturing_closure_ledger,
)


# ============================================================
# Functions
# ============================================================


async def sync_food_ledger_additive_manufacturing_closure() -> int:
    """Replace this ledger with a whole pass of its 식품안전나라 feed.

    The ledger is `food_ledger_additive_manufacturing_closure`.
    The feed is `search-food-additive-manufacturing-closure`.

    One job, one ledger: this walk has its own schedule row, its own run and
    its own steps, and no other ledger waits behind it. The feed is a file
    (I2813, gzip 41KB, 1,707 rows on 2026-09-23), read in chunks of
    `PAGE_SIZE`; no cursor and no `total_count`, so the ledger after a pass
    *is* the pass.

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
    total = asyncio.run(sync_food_ledger_additive_manufacturing_closure())
    print(f"Changed {total} ledger rows")
