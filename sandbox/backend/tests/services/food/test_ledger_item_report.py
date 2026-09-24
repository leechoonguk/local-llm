"""FoodLedgerItemReportService tests — CRUD contracts and the ledger upsert the batch runs."""

import pytest

from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.services.food.ledger_item_report import FoodLedgerItemReportService
from tests.services.food.helpers import ledger_rows, pages


ITEM_REPORT_NO = "1955050900169"

SYNCED_BY = "batch:sync_food_item_report_ledger"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I1250 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "item_report_no": ITEM_REPORT_NO,
        "license_no": "19550509001",
        "business_name": "매일식품주식회사",
        "permit_date": "20030825",
        "product_name": "진미순간장",
        "product_type_name": "혼합간장",
        "production_ended": "아니오",
        "usage_method": "조리시 적절하게 첨가하여 이용한다",
        "domestic_export_type": "O",
        "last_updated_date": "20260701",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_replace_item_report_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerItemReport)

    async with pinned() as session:
        assert await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReport)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_item_report_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages([_record(production_ended="예", last_updated_date="20260901")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReport)
        assert len(rows) == 1
        assert rows[0].production_ended == "예"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_item_report_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages(
                [
                    _record(),
                    _record(item_report_no="   "),
                    _record(item_report_no=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerItemReport)) == 1


@pytest.mark.asyncio
async def test_replace_item_report_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await FoodLedgerItemReportService(session).replace_item_report_ledger(
            pages([_record(last_updated_date="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReport)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
