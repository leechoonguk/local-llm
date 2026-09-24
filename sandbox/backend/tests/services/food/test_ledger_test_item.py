"""FoodLedgerTestItemService tests — CRUD contracts and the ledger upsert the batch runs."""

import pytest

from app.models.food.ledger_test_item import FoodLedgerTestItem
from app.services.food.ledger_test_item import FoodLedgerTestItemService
from tests.services.food.helpers import ledger_rows, pages


TEST_ITEM_CODE = "A10001"

SYNCED_BY = "batch:sync_mfds_ledgers"


def _service(session) -> FoodLedgerTestItemService:
    return FoodLedgerTestItemService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2530 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "test_item_code": TEST_ITEM_CODE,
        "korean_name": "가용성염류",
        "english_name": "Soluble salts",
        "abbreviation": "",
        "alias": "",
        "test_item_name": "가용성염류",
        "major_class_sequence": "2014001001",
        "major_class_code": "A",
        "major_class_korean_name": "일반성분 및 기능성분",
        "middle_class_sequence": "2014001011",
        "middle_class_code": "A1",
        "middle_class_korean_name": "일반성분",
        "residue_definition": "",
        "in_use": "Y",
        "last_updated_at": "2020-03-18 08:53:50.199009",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_test_item_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerTestItem)

    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerTestItem)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_test_item_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_test_item_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(
            pages([_record(in_use="N", last_updated_at="2026-09-01 00:00:00.0")]),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerTestItem)
        assert len(rows) == 1
        assert rows[0].in_use == "N"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_test_item_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(
            pages(
                [
                    _record(),
                    _record(test_item_code="   "),
                    _record(test_item_code=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerTestItem)) == 1


@pytest.mark.asyncio
async def test_test_item_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_test_item_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerTestItem)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
