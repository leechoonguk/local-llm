"""FoodLedgerBarcodeService tests — the ledger the 식품안전나라 batch replaces."""

import pytest

from app.models.food.ledger_barcode import FoodLedgerBarcode
from app.services.food.ledger_barcode import FoodLedgerBarcodeService
from tests.services.food.helpers import ledger_rows, pages


BARCODE_NO = "8805522061018"

ITEM_REPORT_NO = "19950129282236"

SYNCED_BY = "batch:sync_mfds_ledgers"


def _service(session) -> FoodLedgerBarcodeService:
    return FoodLedgerBarcodeService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical C005 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "barcode_no": BARCODE_NO,
        "item_report_no": ITEM_REPORT_NO,
        "permit_date": "20090724",
        "production_end_date": "20200217",
        "product_name": "좋은상품 유기농 부침가루",
        "shelf_life": "제조일로부터 12개월까지",
        "product_type_name": "기타가공품",
        "business_name": "사조동아원(주) 부산공장",
        "industry_name": "식품제조가공업",
        "site_address": "부산광역시 동구",
        "closed_business_date": "",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_barcode_ledger_after_a_second_pass_is_the_second_pass(factory, pinned) -> None:
    """A re-sent row is written again, under the id its pair mints."""
    async with pinned() as session:
        assert await _service(session).replace_barcode_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerBarcode)

    async with pinned() as session:
        assert await _service(session).replace_barcode_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerBarcode)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_barcode_ledger_keeps_a_product_under_each_of_its_barcodes(
    factory,
    pinned,
) -> None:
    """The key is the pair, so one report number with two barcodes is two rows.

    Measured over the whole feed (2026-09-12): 149,006 report numbers carry
    229,040 barcodes, so a ledger keyed on either half alone would drop most
    of what this feed exists to carry.
    """
    async with pinned() as session:
        assert await _service(session).replace_barcode_ledger(
            pages([_record(), _record(barcode_no="8805522061025")]),
            SYNCED_BY,
        ) == (2, 2)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerBarcode)
        assert {row.barcode_no for row in rows} == {BARCODE_NO, "8805522061025"}
        assert {row.item_report_no for row in rows} == {ITEM_REPORT_NO}


@pytest.mark.asyncio
async def test_barcode_ledger_folds_a_pair_the_feed_repeats(factory, pinned) -> None:
    """13,474 of the feed's 259,669 records repeat a pair; the ledger holds one row."""
    async with pinned() as session:
        assert await _service(session).replace_barcode_ledger(
            pages([_record(), _record(product_name="같은 짝, 다른 읽기")]),
            SYNCED_BY,
        ) == (2, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerBarcode)
        assert len(rows) == 1
        assert rows[0].product_name == "좋은상품 유기농 부침가루"


@pytest.mark.asyncio
async def test_barcode_ledger_skips_records_missing_half_the_pair(factory, pinned) -> None:
    """Either half missing leaves a row no later pass could match, so it is dropped."""
    async with pinned() as session:
        assert await _service(session).replace_barcode_ledger(
            pages(
                [
                    _record(),
                    _record(barcode_no="   "),
                    _record(item_report_no=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerBarcode)) == 1
