"""FoodItemReportService tests — CRUD contracts and the ledger upsert the batch runs."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.item_report import (
    FoodItemReportCreateRequest,
    FoodItemReportUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.item_report import FoodItemReportService


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
async def test_food_item_report_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await FoodItemReportService(session).create_item_report(
            FoodItemReportCreateRequest(item_report_no=ITEM_REPORT_NO, product_name="진미순간장"),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await FoodItemReportService(session).get_item_report(row_id)
        assert stored.product_name == "진미순간장"
        assert to_read(stored).item_report_no == ITEM_REPORT_NO

    async with factory() as session:
        rows = await FoodItemReportService(session).list_item_reports()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await FoodItemReportService(session).update_item_report(
            row_id,
            FoodItemReportUpdateRequest(product_name="진미양조간장"),
            updated_by="tester",
        )
        assert updated.product_name == "진미양조간장"

    async with factory() as session:
        await FoodItemReportService(session).delete_item_report(row_id)

    async with factory() as session:
        assert await FoodItemReportService(session).list_item_reports() == []


@pytest.mark.asyncio
async def test_food_item_report_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodItemReportService(session).get_item_report(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodItemReportService(session).update_item_report(
                missing,
                FoodItemReportUpdateRequest(product_name="x"),
                updated_by="tester",
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodItemReportService(session).delete_item_report(missing)


@pytest.mark.asyncio
async def test_update_item_report_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory,
) -> None:
    """Re-reading a window must not rewrite it.

    Every incremental run overlaps the cursor's own row, so a page that always
    wrote would bump `version` and `updated_at` on rows nothing changed about
    — and "this row changed" would stop meaning anything.
    """
    async with factory() as session:
        assert await FoodItemReportService(session).update_item_report_ledger(
            [_record()], SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        assert await FoodItemReportService(session).update_item_report_ledger(
            [_record()], SYNCED_BY
        ) == (1, 0)

    async with factory() as session:
        rows = await FoodItemReportService(session).list_item_reports()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_update_item_report_ledger_refreshes_a_changed_record(factory) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with factory() as session:
        await FoodItemReportService(session).update_item_report_ledger([_record()], SYNCED_BY)

    async with factory() as session:
        assert await FoodItemReportService(session).update_item_report_ledger(
            [_record(production_ended="예", last_updated_date="20260901")], SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await FoodItemReportService(session).list_item_reports()
        assert len(rows) == 1
        assert rows[0].production_ended == "예"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_update_item_report_ledger_skips_records_without_a_code(factory) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with factory() as session:
        assert await FoodItemReportService(session).update_item_report_ledger(
            [_record(item_report_no="   "), _record(item_report_no=None), "not-a-record"],
            SYNCED_BY,
        ) == (3, 0)

    async with factory() as session:
        assert await FoodItemReportService(session).list_item_reports() == []


@pytest.mark.asyncio
async def test_update_item_report_ledger_accepts_a_single_record_payload(factory) -> None:
    """An operation mapping absolute pointers hands back one record, not a page.

    The ledger has to store it rather than iterate a dict's keys — which is
    what a bare `for record in payload` would silently do.
    """
    async with factory() as session:
        assert await FoodItemReportService(session).update_item_report_ledger(
            _record(), SYNCED_BY
        ) == (1, 1)


@pytest.mark.asyncio
async def test_update_item_report_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
) -> None:
    """An unparseable 최종수정일시 costs the cursor, never the record."""
    async with factory() as session:
        await FoodItemReportService(session).update_item_report_ledger(
            [_record(last_updated_date="어제")], SYNCED_BY
        )

    async with factory() as session:
        rows = await FoodItemReportService(session).list_item_reports()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
