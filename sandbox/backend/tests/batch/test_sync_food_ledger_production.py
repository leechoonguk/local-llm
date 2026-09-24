"""Batch job test — sync_food_ledger_production."""

import pytest

import app.batch.sync_food_ledger_production as job_module
from app.batch.sync_food_ledger_production import sync_food_ledger_production
from app.models.food.ledger_production import FoodLedgerProduction
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_production_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-production`
    fills `food_ledger_production`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_production,
        job_module,
        FoodLedgerProduction,
    )
