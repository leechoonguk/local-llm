"""FoodLedgerItemReportRawMaterialService tests — CRUD and the ledger upsert the batch runs."""

import pytest

from app.models.food.ledger_item_report_raw_material import FoodLedgerItemReportRawMaterial
from app.services.food.ledger_item_report_raw_material import FoodLedgerItemReportRawMaterialService
from tests.services.food.helpers import ledger_rows, pages


ITEM_REPORT_NO = "1997040105528"

SYNCED_BY = "batch:sync_food_item_report_raw_material_ledger"


def _service(session) -> FoodLedgerItemReportRawMaterialService:
    return FoodLedgerItemReportRawMaterialService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical C002 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "item_report_no": ITEM_REPORT_NO,
        "license_no": "19970401055",
        "business_name": "주식회사 금성에프앤비",
        "permit_date": "20020409",
        "product_name": "가시오가피 냉면",
        "product_type_name": "숙면",
        "raw_material_names": "밀가루, 정제수, 타피오카전분, 가시오갈피분말, 알카리제, 정제염",
        "raw_material_ordinals": "7,8,9,10,11,12",
        "domestic_export_type": "N",
        "changed_date": "20230610",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_raw_material_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerItemReportRawMaterial)

    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_raw_material_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
            pages([_record(raw_material_names="밀가루, 정제수", changed_date="20260901")]),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].raw_material_names == "밀가루, 정제수"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_raw_material_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
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
        assert len(await ledger_rows(session, FoodLedgerItemReportRawMaterial)) == 1


@pytest.mark.asyncio
async def test_raw_material_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 변경일자 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_item_report_raw_material_ledger(
            pages([_record(changed_date="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
