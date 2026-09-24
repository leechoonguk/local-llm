"""Batch job test — sync_food_ledger_health_functional_item_report."""

import pytest

import app.batch.sync_food_ledger_health_functional_item_report as job_module
from app.batch.sync_food_ledger_health_functional_item_report import (
    sync_food_ledger_health_functional_item_report,
)
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_health_functional_item_report_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-health-functional-item-report`
    fills `food_ledger_health_functional_item_report`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_health_functional_item_report,
        job_module,
        FoodLedgerHealthFunctionalItemReport,
    )
