"""Batch job test — sync_food_ledger_product_classification."""

import pytest

import app.batch.sync_food_ledger_product_classification as job_module
from app.batch.sync_food_ledger_product_classification import (
    sync_food_ledger_product_classification,
)
from app.models.food.ledger_product_classification import FoodLedgerProductClassification
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_product_classification_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-product-classification`
    fills `food_ledger_product_classification`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_product_classification,
        job_module,
        FoodLedgerProductClassification,
    )
