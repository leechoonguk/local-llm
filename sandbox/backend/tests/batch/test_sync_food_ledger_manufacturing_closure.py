"""Batch job test — sync_food_ledger_manufacturing_closure."""

import pytest

import app.batch.sync_food_ledger_manufacturing_closure as job_module
from app.batch.sync_food_ledger_manufacturing_closure import (
    sync_food_ledger_manufacturing_closure,
)
from app.models.food.ledger_manufacturing_closure import (
    FoodLedgerManufacturingClosure,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_manufacturing_closure_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-manufacturing-closure` fills `food_ledger_manufacturing_closure`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_manufacturing_closure,
        job_module,
        FoodLedgerManufacturingClosure,
    )
