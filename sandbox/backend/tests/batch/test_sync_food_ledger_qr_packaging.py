"""Batch job test — sync_food_ledger_qr_packaging."""

import pytest

import app.batch.sync_food_ledger_qr_packaging as job_module
from app.batch.sync_food_ledger_qr_packaging import sync_food_ledger_qr_packaging
from app.models.food.ledger_qr_packaging import FoodLedgerQrPackaging
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_packaging_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-packaging`
    fills `food_ledger_qr_packaging`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_packaging,
        job_module,
        FoodLedgerQrPackaging,
    )
