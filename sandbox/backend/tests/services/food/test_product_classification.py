"""FoodProductClassificationService tests — CRUD contracts and the ledger upsert the batch runs."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.product_classification import (
    FoodProductClassificationCreateRequest,
    FoodProductClassificationUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.product_classification import FoodProductClassificationService
from tests.services.food.helpers import pages


PRODUCT_CODE = "A0100000000000"

SYNCED_BY = "batch:sync_mfds_ledgers"


def _service(session) -> FoodProductClassificationService:
    return FoodProductClassificationService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2510 record, in the keys the operation's fields map to."""
    record: dict[str, object] = {
        "level": "2",
        "product_code": PRODUCT_CODE,
        "korean_name": "곡류",
        "english_name": "",
        "definition": "",
        "valid_begin_date": "20140101",
        "valid_end_date": "99991231",
        "parent_product_code": "A0000000000000",
        "root_product_code": "A0000000000000",
        "mixture_product_yn": "N",
        "attribute_seq": "",
        "attribute_korean_name": "",
        "product_yn": "N",
        "update_reason": "최초등록",
        "use_yn": "Y",
        "remark": "",
        "food_group_yn": "N",
        "last_updated_at": "2021-06-18 11:15:36.860505",
        "child_favorite_food_yn": "N",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_food_product_classification_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await _service(session).create_product_classification(
            FoodProductClassificationCreateRequest(product_code=PRODUCT_CODE, korean_name="곡류"),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await _service(session).get_product_classification(row_id)
        assert stored.korean_name == "곡류"
        assert to_read(stored).product_code == PRODUCT_CODE

    async with factory() as session:
        rows = await _service(session).list_product_classifications()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await _service(session).update_product_classification(
            row_id,
            FoodProductClassificationUpdateRequest(korean_name="곡류 및 그 제품"),
            updated_by="tester",
        )
        assert updated.korean_name == "곡류 및 그 제품"

    async with factory() as session:
        await _service(session).delete_product_classification(row_id)

    async with factory() as session:
        assert await _service(session).list_product_classifications() == []


@pytest.mark.asyncio
async def test_food_product_classification_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).get_product_classification(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).update_product_classification(
                missing,
                FoodProductClassificationUpdateRequest(korean_name="x"),
                updated_by="tester",
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await _service(session).delete_product_classification(missing)


@pytest.mark.asyncio
async def test_product_classification_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory,
    pinned,
) -> None:
    """A pass that re-sends a row unchanged must not rewrite it.

    Every night reads the whole feed, so a merge that always wrote would bump
    `version` and `updated_at` on every row of the ledger - and "this row
    changed" would stop meaning anything.
    """
    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 0)

    async with factory() as session:
        rows = await _service(session).list_product_classifications()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_product_classification_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_product_classification_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages([_record(use_yn="N", last_updated_at="2026-09-01 00:00:00.0")]),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await _service(session).list_product_classifications()
        assert len(rows) == 1
        assert rows[0].use_yn == "N"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_product_classification_ledger_skips_records_without_a_code(factory, pinned) -> None:
    """A record with no code cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages(
                [
                    _record(),
                    _record(product_code="   "),
                    _record(product_code=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await _service(session).list_product_classifications()) == 1


@pytest.mark.asyncio
async def test_product_classification_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_product_classification_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await _service(session).list_product_classifications()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
