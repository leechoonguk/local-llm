"""Batch job test — sync_food_ledger_qr_nutrition."""

import pytest

import app.batch.sync_food_ledger_qr_nutrition as job_module
from app.batch.sync_food_ledger_qr_nutrition import sync_food_ledger_qr_nutrition
from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_nutrition_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-nutrition`
    fills `food_ledger_qr_nutrition`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_nutrition,
        job_module,
        FoodLedgerQrNutrition,
    )
