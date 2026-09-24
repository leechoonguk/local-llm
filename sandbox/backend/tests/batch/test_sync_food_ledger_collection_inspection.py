"""Batch job test — sync_food_ledger_collection_inspection."""

import pytest

import app.batch.sync_food_ledger_collection_inspection as job_module
from app.batch.sync_food_ledger_collection_inspection import sync_food_ledger_collection_inspection
from app.models.food.ledger_collection_inspection import FoodLedgerCollectionInspection
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_collection_inspection_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-collection-inspection` fills `food_ledger_collection_inspection`:
    2,046,194 rows in 2,047 windows (2026-09-18).
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_collection_inspection,
        job_module,
        FoodLedgerCollectionInspection,
    )
