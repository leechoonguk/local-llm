"""Batch job test — sync_food_ledger_import_food_label."""

import pytest

import app.batch.sync_food_ledger_import_food_label as job_module
from app.batch.sync_food_ledger_import_food_label import sync_food_ledger_import_food_label
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_import_food_label_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-import-food-label`
    fills `food_ledger_import_food_label`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_import_food_label,
        job_module,
        FoodLedgerImportFoodLabel,
    )
