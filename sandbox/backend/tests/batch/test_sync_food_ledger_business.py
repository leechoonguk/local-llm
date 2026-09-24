"""Batch job test — sync_food_ledger_business."""

import pytest

import app.batch.sync_food_ledger_business as job_module
from app.batch.sync_food_ledger_business import (
    sync_food_ledger_business,
)
from app.models.food.ledger_business import (
    FoodLedgerBusiness,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_business_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-business` fills `food_ledger_business`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_business,
        job_module,
        FoodLedgerBusiness,
    )
