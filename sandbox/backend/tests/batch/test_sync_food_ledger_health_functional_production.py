"""Batch job test — sync_food_ledger_health_functional_production."""

import pytest

import app.batch.sync_food_ledger_health_functional_production as job_module
from app.batch.sync_food_ledger_health_functional_production import (
    sync_food_ledger_health_functional_production,
)
from app.models.food.ledger_health_functional_production import FoodLedgerHealthFunctionalProduction
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_health_functional_production_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-health-functional-production`
    fills `food_ledger_health_functional_production`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_health_functional_production,
        job_module,
        FoodLedgerHealthFunctionalProduction,
    )
