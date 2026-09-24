"""Batch job test — sync_food_ledger_nutrition."""

import pytest

import app.batch.sync_food_ledger_nutrition as job_module
from app.batch.sync_food_ledger_nutrition import sync_food_ledger_nutrition
from app.models.food.ledger_nutrition import FoodLedgerNutrition
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_nutrition_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-nutrition`
    fills `food_ledger_nutrition`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_nutrition,
        job_module,
        FoodLedgerNutrition,
    )
