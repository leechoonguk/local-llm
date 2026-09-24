"""FoodLedgerLivestockItemReportRawMaterialService tests — CRUD contracts and the ledger upsert."""

from datetime import datetime

import pytest

from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.services.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterialService,
)
from tests.services.food.helpers import ledger_rows, pages


ITEM_REPORT_NO = "199900307705"

SYNCED_BY = "batch:sync_food_livestock_item_report_raw_material_ledger"


def _service(session) -> FoodLedgerLivestockItemReportRawMaterialService:
    return FoodLedgerLivestockItemReportRawMaterialService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical C006 record (window 1/2, 2026-09-07), in the operation's field names."""
    record: dict[str, object] = {
        "item_report_no": ITEM_REPORT_NO,
        "license_no": "19990030770",
        "business_name": "노벨유통",
        "permit_date": "20040131",
        "product_name": "닭꼬치",
        "product_type_name": "포장육",
        "raw_material_names": "닭고기",
        "raw_material_ordinals": "1",
        "changed_date": "20151102",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_livestock_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)

    async with pinned() as session:
        assert await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_livestock_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages([_record(raw_material_names="닭고기, 정제수", changed_date="20260901")]),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].raw_material_names == "닭고기, 정제수"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_livestock_ledger_counts_a_repeated_key_once(factory, pinned) -> None:
    """A key the pass sends twice is one row, and the latest `CHNG_DT` stands.

    Measured on C006 (2026-09-08, whole feed): 1,627 keys came more than once
    in 569,537 records, revisions of one report under one number - the
    oldest a shell with no 원재료 list, the newest the record that replaced
    it. The stage keeps the newest whether the readings share a page or not,
    and a reading with no stamp loses to one with a stamp.
    """
    async with pinned() as session:
        assert await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages(
                [
                    _record(
                        product_name="Shelf Stable Cheddar",
                        raw_material_names="",
                        raw_material_ordinals="",
                        changed_date="20161023",
                    ),
                    _record(
                        product_name="베이컨",
                        raw_material_names="돼지고기, 정제소금",
                        raw_material_ordinals="1,2",
                        changed_date="20231016",
                    ),
                ],
                [
                    _record(
                        product_name="옛 판", raw_material_names="닭고기", changed_date="20191202"
                    )
                ],
                [_record(product_name="날짜 없음", changed_date="")],
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)
        assert [row.product_name for row in rows] == ["베이컨"]
        # SQLite hands the column back without its offset; the portal stamp is KST
        newest = datetime(2023, 10, 15, 15, 0, 0, 0)
        assert rows[0].source_updated_at == newest


@pytest.mark.asyncio
async def test_livestock_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_livestock_item_report_raw_material_ledger(
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
        assert len(await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)) == 1


@pytest.mark.asyncio
async def test_livestock_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 변경일자 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_livestock_item_report_raw_material_ledger(
            pages([_record(changed_date="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerLivestockItemReportRawMaterial)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
