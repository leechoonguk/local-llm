"""Batch job test — sync_food_ledger_recall."""

import pytest

import app.batch.sync_food_ledger_recall as job_module
from app.batch.sync_food_ledger_recall import sync_food_ledger_recall
from app.models.food.ledger_recall import FoodLedgerRecall
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_recall_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-recall`
    fills `food_ledger_recall`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_recall,
        job_module,
        FoodLedgerRecall,
    )
