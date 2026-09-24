"""Batch job test — sync_food_ledger_common_standard_exclusion."""

import pytest

import app.batch.sync_food_ledger_common_standard_exclusion as job_module
from app.batch.sync_food_ledger_common_standard_exclusion import (
    sync_food_ledger_common_standard_exclusion,
)
from app.models.food.ledger_common_standard_exclusion import FoodLedgerCommonStandardExclusion
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_common_standard_exclusion_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-common-standard-exclusion`
    fills `food_ledger_common_standard_exclusion`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_common_standard_exclusion,
        job_module,
        FoodLedgerCommonStandardExclusion,
    )
