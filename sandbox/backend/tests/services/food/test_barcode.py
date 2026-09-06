"""FoodBarcodeService tests — CRUD contracts and the ledger upsert the batch runs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.barcode import (
    FoodBarcodeCreateRequest,
    FoodBarcodeUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.barcode import FoodBarcodeService


BARCODE_NO = "8801234567890"

REPORT_NO = "F2024000123456"

SYNCED_BY = "batch:sync_food_barcode_ledger"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2570 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "report_no": REPORT_NO,
        "report_item_name": "냉동김치",
        "product_name": "신선배 김치",
        "company_name": "(주)김치공방",
        "barcode_no": BARCODE_NO,
        "upper_product_classification_name": "발효식품",
        "top_product_classification_name": "식품",
        "last_update_datetime": "2024-01-15 09:30:00.0",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_food_barcode_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await FoodBarcodeService(session).create_barcode(
            FoodBarcodeCreateRequest(
                barcode_no=BARCODE_NO, report_no=REPORT_NO, product_name="김치"
            ),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        assert (await FoodBarcodeService(session).get_barcode(row_id)).product_name == "김치"

    async with factory() as session:
        assert len(await FoodBarcodeService(session).list_barcodes()) == 1

    async with factory() as session:
        updated = await FoodBarcodeService(session).update_barcode(
            row_id, FoodBarcodeUpdateRequest(product_name="묵은지"), updated_by="tester"
        )
        assert updated.product_name == "묵은지"

    async with factory() as session:
        await FoodBarcodeService(session).delete_barcode(row_id)

    async with factory() as session:
        assert await FoodBarcodeService(session).list_barcodes() == []


@pytest.mark.asyncio
async def test_food_barcode_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodBarcodeService(session).get_barcode(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodBarcodeService(session).update_barcode(
                missing, FoodBarcodeUpdateRequest(product_name="x"), updated_by="tester"
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodBarcodeService(session).delete_barcode(missing)


@pytest.mark.asyncio
async def test_update_barcode_ledger_inserts_then_leaves_unchanged_rows_alone(factory) -> None:
    """Re-reading a window must not rewrite it.

    Every incremental run overlaps the cursor's own day, so a page that always
    wrote would bump `version` and `updated_at` on rows nothing changed about
    — and "this row changed" would stop meaning anything.
    """
    async with factory() as session:
        service = FoodBarcodeService(session)
        assert await service.update_barcode_ledger([_record()], SYNCED_BY) == (1, 1)

    async with factory() as session:
        service = FoodBarcodeService(session)
        assert await service.update_barcode_ledger([_record()], SYNCED_BY) == (1, 0)

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_update_barcode_ledger_refreshes_a_changed_record(factory) -> None:
    """A changed column is what the provider's 변경일자 filter promises to deliver."""
    async with factory() as session:
        await FoodBarcodeService(session).update_barcode_ledger([_record()], SYNCED_BY)

    async with factory() as session:
        received, written = await FoodBarcodeService(session).update_barcode_ledger(
            [_record(product_name="총각김치", last_update_datetime="2024-06-01 12:00:00.0")],
            SYNCED_BY,
        )
        assert (received, written) == (1, 1)

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()
        assert len(rows) == 1
        assert rows[0].product_name == "총각김치"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_update_barcode_ledger_skips_records_without_a_natural_key(factory) -> None:
    """A record with no key cannot be matched again, so it must not be stored.

    The provider leaves columns empty on sparse rows; storing one would insert
    a duplicate on every later run and no query could ever find it.
    """
    async with factory() as session:
        received, written = await FoodBarcodeService(session).update_barcode_ledger(
            [_record(barcode_no="   "), _record(report_no=None), "not-a-record"],
            SYNCED_BY,
        )
        assert (received, written) == (3, 0)

    async with factory() as session:
        assert await FoodBarcodeService(session).list_barcodes() == []


@pytest.mark.asyncio
async def test_update_barcode_ledger_accepts_a_single_record_payload(factory) -> None:
    """An operation mapping absolute pointers hands back one record, not a page.

    The ledger has to store it rather than iterate a dict's keys — which is
    what a bare `for record in payload` would silently do.
    """
    async with factory() as session:
        service = FoodBarcodeService(session)
        assert await service.update_barcode_ledger(_record(), SYNCED_BY) == (1, 1)


@pytest.mark.asyncio
async def test_update_barcode_ledger_keeps_a_record_with_an_unreadable_timestamp(factory) -> None:
    """An unparseable 최종수정일시 costs the cursor, never the record.

    Dropping the row would lose a real item because of a formatting change;
    the row is stored and is simply invisible to the high-water mark.
    """
    async with factory() as session:
        await FoodBarcodeService(session).update_barcode_ledger(
            [_record(last_update_datetime="어제")], SYNCED_BY
        )

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None


@pytest.mark.asyncio
async def test_update_barcode_ledger_reads_the_portal_date_only_form(factory) -> None:
    """The portal's sibling services answer `YYYYMMDD` for the same column.

    A parser that only knew the timestamp form would drop the provider's own
    최종수정일시, and the ledger would answer "unknown" for a record that
    states it.
    """
    async with factory() as session:
        await FoodBarcodeService(session).update_barcode_ledger(
            [_record(last_update_datetime="20240115")], SYNCED_BY
        )

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()
        stored = rows[0].source_updated_at
        assert stored is not None
        # SQLite hands `DateTime(timezone=True)` back without its offset; the
        # column is written in UTC, so that is what the naive value means.
        assert stored.replace(tzinfo=UTC) == datetime(2024, 1, 14, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_update_barcode_ledger_accepts_a_record_without_a_timestamp(factory) -> None:
    """A sparse record still belongs in the ledger; it just carries no timestamp."""
    async with factory() as session:
        await FoodBarcodeService(session).update_barcode_ledger(
            [_record(last_update_datetime="")], SYNCED_BY
        )

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None


@pytest.mark.asyncio
async def test_barcode_read_schema_exposes_the_optimistic_lock_version(factory) -> None:
    """A reader of the ledger has to see which revision it holds.

    `version` is what tells a stale write from a fresh one, so the read shape
    carries it — the ledger is written by a nightly job and read concurrently.
    """
    async with factory() as session:
        row = await FoodBarcodeService(session).create_barcode(
            FoodBarcodeCreateRequest(barcode_no=BARCODE_NO, report_no=REPORT_NO),
            created_by="tester",
        )

    async with factory() as session:
        rows = await FoodBarcodeService(session).list_barcodes()

    read = to_read(row)
    assert read.barcode_no == BARCODE_NO
    assert read.version == 1
    assert [item.id for item in to_read_list(rows)] == [row.id]
