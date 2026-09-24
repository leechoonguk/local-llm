"""FoodLedgerCommonStandardExclusionService tests — CRUD contracts and the ledger upsert.

The record is a measured I2610 row (2026-09-07, 메주 C0120010000000 struck
out of group 000008 for 시험항목 C20004), in the operation's field names.
"""

from datetime import datetime

import pytest

from app.models.food.ledger_common_standard_exclusion import FoodLedgerCommonStandardExclusion
from app.services.food.ledger_common_standard_exclusion import (
    FoodLedgerCommonStandardExclusionService,
)
from tests.services.food.helpers import ledger_rows, pages


COMMON_STANDARD_TYPE_CODE = "000008"

PRODUCT_CODE = "C0120010000000"

TEST_ITEM_CODE = "C20004"

SYNCED_BY = "batch:sync_food_common_standard_exclusion_ledger"


def _service(session) -> FoodLedgerCommonStandardExclusionService:
    return FoodLedgerCommonStandardExclusionService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2610 record (measured 2026-09-07), in the operation's field names."""
    record: dict[str, object] = {
        "common_standard_type_code": "000008",
        "standard_name": "(2) 그 외의 가공식품",
        "product_code": "C0120010000000",
        "product_name": "메주",
        "test_item_code": "C20004",
        "last_updated_at": "2020-12-04 10:45:52.703674",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_common_standard_exclusion_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_exclusion_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerCommonStandardExclusion)

    async with pinned() as session:
        assert await _service(session).replace_common_standard_exclusion_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardExclusion)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_exclusion_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_common_standard_exclusion_ledger(
            pages([_record()]), SYNCED_BY
        )

    async with pinned() as session:
        assert await _service(session).replace_common_standard_exclusion_ledger(
            pages(
                [_record(product_name="메주(재래식)", last_updated_at="2026-09-01 00:00:00.000000")]
            ),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardExclusion)
        assert len(rows) == 1
        assert rows[0].product_name == "메주(재래식)"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_exclusion_ledger_counts_a_repeated_key_once(factory, pinned) -> None:
    """A key the pass sends twice is one row, and the first reading stands.

    Not seen on I2610 (the measured feed never repeats the triple);
    measured on C006, where a stage that inserted both readings would have
    the merge fail on the ledger's unique key and lose the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_exclusion_ledger(
            pages(
                [_record(last_updated_at="2020-12-04 10:45:52.703674")],
                [_record(last_updated_at="2020-01-01 00:00:00.000000")],
            ),
            SYNCED_BY,
        ) == (2, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardExclusion)
        assert len(rows) == 1
        # SQLite hands the column back without its offset; the portal stamp is KST
        first = datetime(2020, 12, 4, 1, 45, 52, 703674)
        assert rows[0].source_updated_at == first


@pytest.mark.asyncio
async def test_common_standard_exclusion_ledger_skips_records_without_a_key(
    factory, pinned
) -> None:
    """A record with no key cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_exclusion_ledger(
            pages(
                [
                    _record(),
                    _record(common_standard_type_code="   "),
                    _record(common_standard_type_code=None),
                    _record(product_code="   "),
                    _record(product_code=None),
                    _record(test_item_code="   "),
                    _record(test_item_code=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (8, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerCommonStandardExclusion)) == 1


@pytest.mark.asyncio
async def test_common_standard_exclusion_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_common_standard_exclusion_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardExclusion)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
