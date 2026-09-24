"""Batch job test — sync_food_ledger_inspection_failure."""

import pytest

import app.batch.sync_food_ledger_inspection_failure as job_module
from app.batch.sync_food_ledger_inspection_failure import sync_food_ledger_inspection_failure
from app.models.food.ledger_inspection_failure import FoodLedgerInspectionFailure
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_inspection_failure_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-inspection-failure`
    fills `food_ledger_inspection_failure`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_inspection_failure,
        job_module,
        FoodLedgerInspectionFailure,
    )
