"""Batch job test — sync_food_ledger_qr_caution."""

import pytest

import app.batch.sync_food_ledger_qr_caution as job_module
from app.batch.sync_food_ledger_qr_caution import sync_food_ledger_qr_caution
from app.models.food.ledger_qr_caution import FoodLedgerQrCaution
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_caution_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-caution`
    fills `food_ledger_qr_caution`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_caution,
        job_module,
        FoodLedgerQrCaution,
    )
