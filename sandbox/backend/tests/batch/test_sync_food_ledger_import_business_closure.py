"""Batch job test — sync_food_ledger_import_business_closure."""

import pytest

import app.batch.sync_food_ledger_import_business_closure as job_module
from app.batch.sync_food_ledger_import_business_closure import (
    sync_food_ledger_import_business_closure,
)
from app.models.food.ledger_import_business_closure import (
    FoodLedgerImportBusinessClosure,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_import_business_closure_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-import-business-closure` fills `food_ledger_import_business_closure`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_import_business_closure,
        job_module,
        FoodLedgerImportBusinessClosure,
    )
