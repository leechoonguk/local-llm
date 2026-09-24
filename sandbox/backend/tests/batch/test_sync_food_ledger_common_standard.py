"""Batch job test — sync_food_ledger_common_standard."""

import pytest

import app.batch.sync_food_ledger_common_standard as job_module
from app.batch.sync_food_ledger_common_standard import sync_food_ledger_common_standard
from app.models.food.ledger_common_standard import FoodLedgerCommonStandard
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_common_standard_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-common-standard`
    fills `food_ledger_common_standard`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_common_standard,
        job_module,
        FoodLedgerCommonStandard,
    )
