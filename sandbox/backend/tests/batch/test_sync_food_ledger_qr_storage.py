"""Batch job test — sync_food_ledger_qr_storage."""

import pytest

import app.batch.sync_food_ledger_qr_storage as job_module
from app.batch.sync_food_ledger_qr_storage import sync_food_ledger_qr_storage
from app.models.food.ledger_qr_storage import FoodLedgerQrStorage
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_storage_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-storage`
    fills `food_ledger_qr_storage`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_storage,
        job_module,
        FoodLedgerQrStorage,
    )
