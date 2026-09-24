"""Batch job test — sync_food_ledger_meat_packaging_closure."""

import pytest

import app.batch.sync_food_ledger_meat_packaging_closure as job_module
from app.batch.sync_food_ledger_meat_packaging_closure import (
    sync_food_ledger_meat_packaging_closure,
)
from app.models.food.ledger_meat_packaging_closure import (
    FoodLedgerMeatPackagingClosure,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_meat_packaging_closure_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-meat-packaging-closure` fills `food_ledger_meat_packaging_closure`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_meat_packaging_closure,
        job_module,
        FoodLedgerMeatPackagingClosure,
    )
