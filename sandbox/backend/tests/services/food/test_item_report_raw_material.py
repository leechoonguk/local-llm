"""FoodItemReportRawMaterialService tests — CRUD contracts and the ledger upsert the batch runs."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.item_report_raw_material import (
    FoodItemReportRawMaterialCreateRequest,
    FoodItemReportRawMaterialUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.item_report_raw_material import FoodItemReportRawMaterialService
from tests.services.food.helpers import pages


ITEM_REPORT_NO = "1997040105528"

SYNCED_BY = "batch:sync_food_item_report_raw_material_ledger"


def _service(session) -> FoodItemReportRawMaterialService:
    return FoodItemReportRawMaterialService(session)


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
async def test_food_item_report_raw_material_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await _service(session).create_item_report_raw_material(
            FoodItemReportRawMaterialCreateRequest(
                item_report_no=ITEM_REPORT_NO, product_name="가시오가피 냉면"
            ),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await _service(session).get_item_report_raw_material(row_id)
        assert stored.product_name == "가시오가피 냉면"
        assert to_read(stored).item_report_no == ITEM_REPORT_NO

    async with factory() as session:
        rows = await _service(session).list_item_report_raw_materials()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await _service(session).update_item_report_raw_material(
            row_id,
            FoodItemReportRawMaterialUpdateRequest(product_name="진미양조간장"),
            updated_by="tester",
        )
        assert updated.product_name == "진미양조간장"

    async with factory() as session:
        await _service(session).delete_item_report_raw_material(row_id)

    async with factory() as session:
        assert await _service(session).list_item_report_raw_materials() == []


@pytest.mark.asyncio
async def test_food_item_report_raw_material_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).get_item_report_raw_material(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).update_item_report_raw_material(
                missing,
                FoodItemReportRawMaterialUpdateRequest(product_name="x"),
                updated_by="tester",
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).delete_item_report_raw_material(missing)


@pytest.mark.asyncio
async def test_raw_material_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory,
    pinned,
) -> None:
    """A pass that re-sends a row unchanged must not rewrite it.

    Every night reads the whole feed, so a merge that always wrote would bump
    `version` and `updated_at` on every row of the ledger - and "this row
    changed" would stop meaning anything.
    """
    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with pinned() as session:
        assert await _service(session).replace_item_report_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 0)

    async with factory() as session:
        rows = await _service(session).list_item_report_raw_materials()
        assert len(rows) == 1
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
        rows = await _service(session).list_item_report_raw_materials()
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
        assert len(await _service(session).list_item_report_raw_materials()) == 1


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
        rows = await _service(session).list_item_report_raw_materials()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
