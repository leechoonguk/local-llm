"""FoodLedgerCommonStandardService tests — CRUD contracts and the ledger upsert.

The record is a measured I2600 row (2026-09-07, serial 2017016593 - one of
the 16 serials the feed repeats, one row per 시험항목), in the operation's
field names.
"""

from datetime import datetime

import pytest

from app.models.food.ledger_common_standard import FoodLedgerCommonStandard
from app.services.food.ledger_common_standard import FoodLedgerCommonStandardService
from tests.services.food.helpers import ledger_rows, pages


COMMON_STANDARD_SEQ = "2017016593"

SYNCED_BY = "batch:sync_food_common_standard_ledger"


def _service(session) -> FoodLedgerCommonStandardService:
    return FoodLedgerCommonStandardService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2600 record (measured 2026-09-07), in the operation's field names."""
    record: dict[str, object] = {
        "common_standard_seq": "2017016593",
        "common_standard_type_code": "000156",
        "common_standard_type_name": "16) 식품의 제조·가공에 사용되는 캡슐류",
        "product_code": "C0000000000000",
        "product_name": "가공식품",
        "test_item_code": "B60038",
        "test_item_name": "보존료",
        "detail_item_name": "파라옥시안식향산메틸",
        "clause_seq": "2016000016",
        "clause_name": "파라옥시안식향산으로서",
        "standard_value": "1.0이하",
        "standard_value_summary": "보존료 : 파라옥시안식향산메틸 : 1.0이하(파라옥시안식향산으로서)",
        "valid_begin_date": "20180101",
        "valid_end_date": "99991231",
        "source_code": "",
        "valid_digits": "1",
        "judgment_format_code": "01",
        "judgment_format_name": "최대/최소",
        "maximum_value": "1.0",
        "maximum_value_type_code": "01",
        "maximum_value_type_name": "이하",
        "minimum_value": "",
        "minimum_value_type_code": "",
        "minimum_value_type_name": "",
        "choice_fit_code": "",
        "choice_fit_name": "",
        "choice_unfit_code": "",
        "choice_unfit_name": "",
        "microbe_2n": "",
        "microbe_2c": "",
        "microbe_2m": "",
        "microbe_3m": "",
        "detail_item_included_yn": "N",
        "hazard_yn": "N",
        "priority_inspection_yn": "N",
        "monitoring_yn": "N",
        "outside_codex_yn": "N",
        "self_inspection_yn": "N",
        "unit_code": "017",
        "unit_name": "g/kg",
        "update_reason": "",
        "last_updated_at": "2023-04-12 16:36:47.227438",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_common_standard_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerCommonStandard)

    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandard)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_common_standard_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages(
                [_record(test_item_name="보존료(합)", last_updated_at="2026-09-01 00:00:00.000000")]
            ),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandard)
        assert len(rows) == 1
        assert rows[0].test_item_name == "보존료(합)"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_common_standard_ledger_counts_a_repeated_key_once(factory, pinned) -> None:
    """A key the pass sends twice is one row, and the first reading stands.

    Not seen on I2600 (the measured feed never repeats the pair); measured
    on C006, where a stage that inserted both readings would have the merge
    fail on the ledger's unique key and lose the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages(
                [_record(last_updated_at="2023-04-12 16:36:47.227438")],
                [_record(last_updated_at="2024-01-01 00:00:00.000000")],
            ),
            SYNCED_BY,
        ) == (2, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandard)
        assert len(rows) == 1
        # SQLite hands the column back without its offset; the portal stamp is KST
        first = datetime(2023, 4, 12, 7, 36, 47, 227438)
        assert rows[0].source_updated_at == first


@pytest.mark.asyncio
async def test_common_standard_ledger_keeps_one_row_per_test_item_of_a_serial(
    factory, pinned
) -> None:
    """A serial the feed lists under several 시험항목 is one row per 시험항목.

    Measured 2026-09-07: 16 serials repeat, 2017016593 three times (메틸
    B60038, 에틸 B60039 and the 적/부 row B60016). Keyed on the serial alone
    the stage would keep the first and drop the other two silently.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages(
                [
                    _record(),
                    _record(
                        test_item_code="B60039",
                        detail_item_name="파라옥시안식향산에틸",
                        standard_value_summary=(
                            "보존료 : 파라옥시안식향산에틸 : 1.0이하(파라옥시안식향산으로서)"
                        ),
                    ),
                ]
            ),
            SYNCED_BY,
        ) == (2, 2)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandard)
        assert sorted(row.test_item_code for row in rows) == ["B60038", "B60039"]


@pytest.mark.asyncio
async def test_common_standard_ledger_skips_records_without_a_key(factory, pinned) -> None:
    """A record with no key cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows (never these two on the
    measured feed); storing one would insert a duplicate on every later run
    and no query could ever find it.
    """
    async with pinned() as session:
        assert await _service(session).replace_common_standard_ledger(
            pages(
                [
                    _record(),
                    _record(common_standard_seq="   "),
                    _record(common_standard_seq=None),
                    _record(test_item_code=""),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (5, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerCommonStandard)) == 1


@pytest.mark.asyncio
async def test_common_standard_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_common_standard_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerCommonStandard)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
