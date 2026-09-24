"""FoodLedgerRawMaterialService tests — CRUD contracts and the ledger upsert the batch runs."""

import pytest

from app.models.food.ledger_raw_material import FoodLedgerRawMaterial
from app.services.food.ledger_raw_material import FoodLedgerRawMaterialService
from tests.services.food.helpers import ledger_rows, pages


RAW_MATERIAL_CODE = "M000012345"

SYNCED_BY = "batch:sync_food_raw_material_ledger"


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2520 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "raw_material_code": RAW_MATERIAL_CODE,
        "representative_raw_material_name": "고춧가루",
        "raw_material_alias": "고추가루",
        "english_name": "Red pepper powder",
        "scientific_name": "Capsicum annuum",
        "raw_material_large_class": "농산물",
        "raw_material_medium_class": "채소류",
        "region_code_name": "국내산",
        "raw_material_status_code_name": "사용가능",
        "valid_start_date": "20200101",
        "use_yn": "Y",
        "last_update_datetime": "20240115",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerRawMaterial)

    async with pinned() as session:
        assert await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerRawMaterial)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages([_record(use_yn="N", last_update_datetime="20240601")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerRawMaterial)
        assert len(rows) == 1
        assert rows[0].use_yn == "N"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages(
                [
                    _record(),
                    _record(raw_material_code="   "),
                    _record(raw_material_code=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerRawMaterial)) == 1


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await FoodLedgerRawMaterialService(session).replace_raw_material_ledger(
            pages([_record(last_update_datetime="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerRawMaterial)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
