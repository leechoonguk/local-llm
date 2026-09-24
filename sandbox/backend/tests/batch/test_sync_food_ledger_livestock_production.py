"""Batch job test — sync_food_ledger_livestock_production."""

import pytest

import app.batch.sync_food_ledger_livestock_production as job_module
from app.batch.sync_food_ledger_livestock_production import sync_food_ledger_livestock_production
from app.models.food.ledger_livestock_production import FoodLedgerLivestockProduction
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_livestock_production_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-livestock-production`
    fills `food_ledger_livestock_production`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_livestock_production,
        job_module,
        FoodLedgerLivestockProduction,
    )
