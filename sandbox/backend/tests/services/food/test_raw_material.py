"""FoodRawMaterialService tests — CRUD contracts and the ledger upsert the batch runs."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.schemas.food.raw_material import (
    FoodRawMaterialCreateRequest,
    FoodRawMaterialFilter,
    FoodRawMaterialUpdateRequest,
    to_read,
    to_read_list,
)
from app.services.food.raw_material import FoodRawMaterialService
from tests.services.food.helpers import pages


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
async def test_food_raw_material_service_crud(factory) -> None:
    """Each step runs in its own session, as the request lifecycle does.

    A read autobegins a transaction, so reusing one session would make the
    next write's `session.begin()` collide instead of exercising the contract.
    """
    async with factory() as session:
        created = await FoodRawMaterialService(session).create_raw_material(
            FoodRawMaterialCreateRequest(
                raw_material_code=RAW_MATERIAL_CODE, representative_raw_material_name="고춧가루"
            ),
            created_by="tester",
        )
        row_id = created.id

    async with factory() as session:
        stored = await FoodRawMaterialService(session).get_raw_material(row_id)
        assert stored.representative_raw_material_name == "고춧가루"
        assert to_read(stored).raw_material_code == RAW_MATERIAL_CODE

    async with factory() as session:
        rows = await FoodRawMaterialService(session).list_raw_materials()
        assert len(to_read_list(rows)) == 1

    async with factory() as session:
        updated = await FoodRawMaterialService(session).update_raw_material(
            row_id,
            FoodRawMaterialUpdateRequest(representative_raw_material_name="건고추"),
            updated_by="tester",
        )
        assert updated.representative_raw_material_name == "건고추"

    async with factory() as session:
        await FoodRawMaterialService(session).delete_raw_material(row_id)

    async with factory() as session:
        assert await FoodRawMaterialService(session).list_raw_materials() == []


@pytest.mark.asyncio
async def test_food_raw_material_service_missing_row_raises_not_found(factory) -> None:
    """404 is the ledger's answer for an id it does not hold, on all three verbs."""
    missing = uuid4()
    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodRawMaterialService(session).get_raw_material(missing)

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodRawMaterialService(session).update_raw_material(
                missing,
                FoodRawMaterialUpdateRequest(representative_raw_material_name="x"),
                updated_by="tester",
            )

    async with factory() as session:
        with pytest.raises(NotFoundError):
            await FoodRawMaterialService(session).delete_raw_material(missing)


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_inserts_then_leaves_unchanged_rows_alone(
    factory,
    pinned,
) -> None:
    """A pass that re-sends a row unchanged must not rewrite it.

    Every night reads the whole feed, so a merge that always wrote would bump
    `version` and `updated_at` on every row of the ledger - and "this row
    changed" would stop meaning anything.
    """
    async with pinned() as session:
        assert await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with pinned() as session:
        assert await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 0)

    async with factory() as session:
        rows = await FoodRawMaterialService(session).list_raw_materials()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages([_record(use_yn="N", last_update_datetime="20240601")]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await FoodRawMaterialService(session).list_raw_materials()
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
        assert await FoodRawMaterialService(session).replace_raw_material_ledger(
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
        assert len(await FoodRawMaterialService(session).list_raw_materials()) == 1


@pytest.mark.asyncio
async def test_replace_raw_material_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages([_record(last_update_datetime="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await FoodRawMaterialService(session).list_raw_materials()
        assert len(rows) == 1
        assert rows[0].source_updated_at is None


@pytest.mark.asyncio
async def test_list_and_count_agree_under_the_same_filters(factory, pinned) -> None:
    """The page and its total are built from one predicate, so they cannot drift.

    A total counted without the filter would make the grid say "1-2 of 3" over
    two matching rows - the footer describing a different collection than the
    one on screen.
    """
    async with pinned() as session:
        await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages(
                [
                    _record(raw_material_code="A1", representative_raw_material_name="고추가루"),
                    _record(raw_material_code="A2", representative_raw_material_name="마늘"),
                    _record(raw_material_code="B1", representative_raw_material_name="고추장"),
                ]
            ),
            SYNCED_BY,
        )

    async with factory() as session:
        service = FoodRawMaterialService(session)
        assert await service.count_raw_materials() == 3
        by_code = FoodRawMaterialFilter(raw_material_code="a")
        assert await service.count_raw_materials(by_code) == 2
        by_name = FoodRawMaterialFilter(representative_raw_material_name="고추")
        rows = await service.list_raw_materials(filters=by_name)
        assert [r.raw_material_code for r in rows] == ["A1", "B1"]
        assert await service.count_raw_materials(by_name) == 2


@pytest.mark.asyncio
async def test_facets_are_the_ledgers_own_values_sorted_without_null(factory, pinned) -> None:
    """A select can only offer what a row holds, and NULL is not a choice."""
    async with pinned() as session:
        await FoodRawMaterialService(session).replace_raw_material_ledger(
            pages(
                [
                    _record(
                        raw_material_code="A1",
                        raw_material_large_class="식물",
                        raw_material_medium_class="채소류",
                    ),
                    _record(
                        raw_material_code="A2",
                        raw_material_large_class="동물",
                        raw_material_medium_class=None,
                    ),
                    _record(
                        raw_material_code="A3",
                        raw_material_large_class="식물",
                        raw_material_medium_class="과일류",
                    ),
                ]
            ),
            SYNCED_BY,
        )

    async with factory() as session:
        facets = await FoodRawMaterialService(session).list_raw_material_facets()
    assert facets.raw_material_large_class == ["동물", "식물"]
    assert facets.raw_material_medium_class == ["과일류", "채소류"]
    assert facets.raw_material_status_code_name == ["사용가능"]
    # The child list per parent: 동물 has rows but none with a medium class, so it
    # has no entry - a parent with no children offers no child, not an empty one.
    assert facets.raw_material_medium_class_by_large == {"식물": ["과일류", "채소류"]}
