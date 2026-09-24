"""Batch job test — sync_food_ledger_test_item."""

import pytest

import app.batch.sync_food_ledger_test_item as job_module
from app.batch.sync_food_ledger_test_item import sync_food_ledger_test_item
from app.models.food.ledger_test_item import FoodLedgerTestItem
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_test_item_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-test-item`
    fills `food_ledger_test_item`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_test_item,
        job_module,
        FoodLedgerTestItem,
    )
