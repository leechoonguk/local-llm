"""FoodLedgerCollectionInspectionService tests - the 수거검사 ledger the mfds batch replaces."""

import pytest

from app.models.food.ledger_collection_inspection import FoodLedgerCollectionInspection
from app.services.food.ledger_collection_inspection import FoodLedgerCollectionInspectionService
from tests.services.food.helpers import ledger_rows, pages


SYNCED_BY = "batch:sync_food_ledger_collection_inspection"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical record, in the keys the operation's fields map to.

    Copied from a measured row (2026-09-18, window 1/2): two specimens of one
    집단급식소, still 검토중, with no 품목제조보고번호 - which is 67.4 % of this
    feed.
    """
    record: dict[str, object] = {
        "collection_no": "0918-대구가을-01",
        "product_name": "수도꼭지",
        "business_name": "유가유치원",
        "address": "대구광역시 달성군",
        "industry_name": "집단급식소",
        "specimen_type": "식품접객업",
        "collected_on": "20260918",
        "judgment": "검토중",
        "institution_name": "대구광역시 보건복지국 위생정책과",
        "item_report_no": "",
        "plan_title": "2026 노로바이러스 감시체계 사업",
        "source_updated_text": "2026-09-18 16:25:59.676351",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_inspection_collapses_two_identical_records(factory, pinned) -> None:
    """A record repeated verbatim is one row, because the key is the record.

    This feed publishes no identifier and repeats itself - 수거증번호 alone
    repeats 651,739 times, and 1,037 rows are identical in all twelve columns -
    so two such rows are one fact told twice, and the digest says so.
    """
    async with pinned() as session:
        assert await FoodLedgerCollectionInspectionService(
            session
        ).replace_collection_inspection_ledger(pages([_record(), _record()]), SYNCED_BY) == (2, 1)

    async with factory() as session:
        (row,) = await ledger_rows(session, FoodLedgerCollectionInspection)
        assert row.product_name == "수도꼭지"
        assert row.item_report_no is None
        assert len(row.record_digest) == 64


@pytest.mark.asyncio
async def test_inspection_keeps_two_specimens_of_one_collection(factory, pinned) -> None:
    """One 수거증 covering two products is two rows, not one.

    The 수거증번호 is shared and the response names nothing that tells the two
    apart except 제품명, so a ledger keyed on the 수거증 would lose one of them.
    """
    async with pinned() as session:
        assert await FoodLedgerCollectionInspectionService(
            session
        ).replace_collection_inspection_ledger(
            pages([_record(), _record(product_name="완구")]), SYNCED_BY
        ) == (2, 2)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCollectionInspection)
        assert sorted(row.product_name or "" for row in rows) == ["수도꼭지", "완구"]
        assert len({row.record_digest for row in rows}) == 2


@pytest.mark.asyncio
async def test_inspection_writes_a_changed_judgment_as_its_own_row(factory, pinned) -> None:
    """A verdict that changed is a different record, and the pass is the ledger.

    0.43 % of this feed reads 부적합 and 21.1 % has no verdict yet, so a row
    moving from 검토중 to 부적합 is the event worth reading. A pass replaces the
    ledger whole, so after it only the current reading is there - what the key
    must not do is match the old verdict and hide the new one.
    """
    async with pinned() as session:
        assert await FoodLedgerCollectionInspectionService(
            session
        ).replace_collection_inspection_ledger(pages([_record()]), SYNCED_BY) == (1, 1)

    async with pinned() as session:
        assert await FoodLedgerCollectionInspectionService(
            session
        ).replace_collection_inspection_ledger(pages([_record(judgment="부적합")]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (row,) = await ledger_rows(session, FoodLedgerCollectionInspection)
        assert row.judgment == "부적합"
        assert row.created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_inspection_skips_records_that_say_nothing(factory, pinned) -> None:
    """A record empty in every column digests to a key and is still not a fact."""
    async with pinned() as session:
        assert await FoodLedgerCollectionInspectionService(
            session
        ).replace_collection_inspection_ledger(
            pages([_record(), {key: "" for key in _record()}, "not-a-record"]), SYNCED_BY
        ) == (3, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerCollectionInspection)) == 1
