"""FoodLedgerCommonStandardTypeService tests — CRUD contracts and the ledger upsert.

The record is a measured I2590 row (2026-09-07, code 000075 - the 공통 기준
chapter under the 건강기능식품 root 000074), in the operation's field names.
"""

from datetime import datetime

import pytest

from app.models.food.ledger_common_standard_type import FoodLedgerCommonStandardType
from app.services.food.ledger_common_standard_type import FoodLedgerCommonStandardTypeService
from tests.services.food.helpers import ledger_rows, pages


COMMON_STANDARD_TYPE_CODE = "000075"

SYNCED_BY = "batch:sync_food_common_standard_type_ledger"


def _service(session) -> FoodLedgerCommonStandardTypeService:
    return FoodLedgerCommonStandardTypeService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2590 record (measured 2026-09-07), in the operation's field names."""
    record: dict[str, object] = {
        "common_standard_type_code": "000075",
        "standard_name": "제 2. 공통 기준 및 규격",
        "parent_common_standard_type_code": "000074",
        "level": "2",
        "definition": "",
        "use_yn": "Y",
        "last_updated_at": "2014-12-02 17:47:39.721066",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_common_standard_type_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_type_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerCommonStandardType)

    async with pinned() as session:
        assert await _service(session).replace_common_standard_type_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardType)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_type_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_common_standard_type_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await _service(session).replace_common_standard_type_ledger(
            pages(
                [
                    _record(
                        standard_name="식품의 기준 및 규격",
                        last_updated_at="2026-09-01 00:00:00.000000",
                    )
                ]
            ),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardType)
        assert len(rows) == 1
        assert rows[0].standard_name == "식품의 기준 및 규격"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_type_ledger_counts_a_repeated_key_once(factory, pinned) -> None:
    """A key the pass sends twice is one row, and the first reading stands.

    Not seen on I2590 (the measured feed never repeats a code); measured on
    C006, where a stage that inserted both readings would have the merge
    fail on the ledger's unique key and lose the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_type_ledger(
            pages(
                [_record(last_updated_at="2019-08-17 16:32:52.644448")],
                [_record(last_updated_at="2020-01-01 00:00:00.000000")],
            ),
            SYNCED_BY,
        ) == (2, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardType)
        assert len(rows) == 1
        # SQLite hands the column back without its offset; the portal stamp is KST
        first = datetime(2019, 8, 17, 7, 32, 52, 644448)
        assert rows[0].source_updated_at == first


@pytest.mark.asyncio
async def test_common_standard_type_ledger_skips_records_without_a_key(factory, pinned) -> None:
    """A record with no key cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows; storing one would insert a
    duplicate on every later run and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_type_ledger(
            pages(
                [
                    _record(),
                    _record(common_standard_type_code="   "),
                    _record(common_standard_type_code=None),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (4, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerCommonStandardType)) == 1


@pytest.mark.asyncio
async def test_common_standard_type_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_common_standard_type_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandardType)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
