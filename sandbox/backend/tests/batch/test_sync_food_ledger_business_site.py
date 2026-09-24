"""Batch job test — sync_food_ledger_business_site."""

import pytest

import app.batch.sync_food_ledger_business_site as job_module
from app.batch.sync_food_ledger_business_site import (
    sync_food_ledger_business_site,
)
from app.models.food.ledger_business_site import (
    FoodLedgerBusinessSite,
)
from tests.batch.ledger_job import assert_job_fills_its_ledger


@pytest.mark.asyncio
async def test_sync_food_ledger_business_site_fills_its_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One job, one feed, one ledger.

    `search-food-business-site` fills `food_ledger_business_site`.
    """
    await assert_job_fills_its_ledger(
        monkeypatch,
        sync_food_ledger_business_site,
        job_module,
        FoodLedgerBusinessSite,
    )
