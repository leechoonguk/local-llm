"""Batch job test — sync_food_ledger_qr_allergy."""

import pytest

import app.batch.sync_food_ledger_qr_allergy as job_module
from app.batch.sync_food_ledger_qr_allergy import sync_food_ledger_qr_allergy
from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_qr_allergy_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-qr-allergy`
    fills `food_ledger_qr_allergy`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_qr_allergy,
        job_module,
        FoodLedgerQrAllergy,
    )
