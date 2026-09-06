"""FoodTestItemService tests — CRUD contracts and the ledger upsert the batch runs."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.test_item import (
    FoodTestItemCreateRequest,
    FoodTestItemUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.test_item import FoodTestItemService
from tests.services.food.helpers import pages


TEST_ITEM_CODE = "A10001"

SYNCED_BY = "batch:sync_mfds_ledgers"


def _service(session) -> FoodTestItemService:
    return FoodTestItemService(session)


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
async def test_food_test_item_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await _service(session).create_test_item(
            FoodTestItemCreateRequest(test_item_code=TEST_ITEM_CODE, korean_name="가용성염류"),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await _service(session).get_test_item(row_id)
        assert stored.korean_name == "가용성염류"
        assert to_read(stored).test_item_code == TEST_ITEM_CODE

    async with factory() as session:
        rows = await _service(session).list_test_items()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await _service(session).update_test_item(
            row_id,
            FoodTestItemUpdateRequest(korean_name="가용성 염류"),
            updated_by="tester",
        )
        assert updated.korean_name == "가용성 염류"

    async with factory() as session:
        await _service(session).delete_test_item(row_id)

    async with factory() as session:
        assert await _service(session).list_test_items() == []


@pytest.mark.asyncio
async def test_food_test_item_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).get_test_item(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).update_test_item(
                missing,
                FoodTestItemUpdateRequest(korean_name="x"),
                updated_by="tester",
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).delete_test_item(missing)


@pytest.mark.asyncio
async def test_test_item_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory,
    pinned,
) -> None:
    """A pass that re-sends a row unchanged must not rewrite it.

    Every night reads the whole feed, so a merge that always wrote would bump
    `version` and `updated_at` on every row of the ledger - and "this row
    changed" would stop meaning anything.
    """
    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            1,
        )

    async with pinned() as session:
        assert await _service(session).replace_test_item_ledger(pages([_record()]), SYNCED_BY) == (
            1,
            0,
        )

    async with factory() as session:
        rows = await _service(session).list_test_items()
        assert len(rows) == 1
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
        rows = await _service(session).list_test_items()
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
        assert len(await _service(session).list_test_items()) == 1


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
        rows = await _service(session).list_test_items()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
