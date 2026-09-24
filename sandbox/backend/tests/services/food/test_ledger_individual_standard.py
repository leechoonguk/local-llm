"""FoodLedgerIndividualStandardService tests — CRUD contracts and the ledger upsert.

The record is a measured I2580 row (2026-09-07, serial 2017001103 유산균음료
세균수 - one of the 322 serials the feed repeats, here across 단서조항), in
the operation's field names.
"""

from datetime import datetime

import pytest

from app.models.food.ledger_individual_standard import FoodLedgerIndividualStandard
from app.services.food.ledger_individual_standard import FoodLedgerIndividualStandardService
from tests.services.food.helpers import ledger_rows, pages


INDIVIDUAL_STANDARD_SEQ = "2017001103"

SYNCED_BY = "batch:sync_food_individual_standard_ledger"


def _service(session) -> FoodLedgerIndividualStandardService:
    return FoodLedgerIndividualStandardService(session)


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2580 record (measured 2026-09-07), in the operation's field names."""
    record: dict[str, object] = {
        "individual_standard_seq": "2017001103",
        "product_code": "C0309060100000",
        "product_name": "유산균음료",
        "test_item_code": "C10002",
        "test_item_name": "세균수",
        "detail_item_name": "세균수",
        "clause_seq": "2022000003",
        "clause_name": "살균제품에 한한다",
        "standard_value": "n=5, c=1, m=100, M=1000",
        "standard_value_summary": "",
        "valid_begin_date": "20180101",
        "valid_end_date": "99991231",
        "source_code": "식품공전(제2022-76호)",
        "valid_digits": "",
        "judgment_format_code": "03",
        "judgment_format_name": "3군법",
        "maximum_value": "",
        "maximum_value_type_code": "",
        "maximum_value_type_name": "",
        "minimum_value": "",
        "minimum_value_type_code": "",
        "minimum_value_type_name": "",
        "choice_fit_code": "",
        "choice_fit_name": "",
        "choice_unfit_code": "",
        "choice_unfit_name": "",
        "microbe_2n": "5",
        "microbe_2c": "1",
        "microbe_2m": "100",
        "microbe_3m": "1000",
        "detail_item_included_yn": "N",
        "hazard_yn": "N",
        "priority_inspection_yn": "N",
        "monitoring_yn": "N",
        "outside_codex_yn": "N",
        "self_inspection_yn": "N",
        "unit_code": "011",
        "unit_name": "CFU/g",
        "update_reason": "최초등록",
        "last_updated_at": "2023-07-03 10:18:46.823081",
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_individual_standard_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerIndividualStandard)

    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerIndividualStandard)
        assert len(rows) == 1
        assert rows[0].id == first.id
        assert rows[0].version == 1
        assert rows[0].created_by == SYNCED_BY


@pytest.mark.asyncio
async def test_individual_standard_ledger_refreshes_a_changed_record(factory, pinned) -> None:
    """A column the portal changed is what the ledger exists to carry forward."""
    async with pinned() as session:
        await _service(session).replace_individual_standard_ledger(pages([_record()]), SYNCED_BY)

    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages(
                [_record(test_item_name="일반세균수", last_updated_at="2026-09-01 00:00:00.000000")]
            ),
            SYNCED_BY,
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerIndividualStandard)
        assert len(rows) == 1
        assert rows[0].test_item_name == "일반세균수"
        assert rows[0].updated_by == SYNCED_BY


@pytest.mark.asyncio
async def test_individual_standard_ledger_counts_a_repeated_key_once(factory, pinned) -> None:
    """A key the pass sends twice is one row, and the first reading stands.

    Not seen on I2580 (the measured feed never repeats the four-column
    key); measured on C006, where a stage that inserted both readings would
    have the merge fail on the ledger's unique key and lose the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages(
                [_record(last_updated_at="2023-07-03 10:18:46.823081")],
                [_record(last_updated_at="2024-01-01 00:00:00.000000")],
            ),
            SYNCED_BY,
        ) == (2, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerIndividualStandard)
        assert len(rows) == 1
        # SQLite hands the column back without its offset; the portal stamp is KST
        first = datetime(2023, 7, 3, 1, 18, 46, 823081)
        assert rows[0].source_updated_at == first


@pytest.mark.asyncio
async def test_individual_standard_ledger_keeps_every_row_of_a_repeated_serial(
    factory, pinned
) -> None:
    """A serial the feed repeats is one row per (시험항목, 세부항목, 단서조항).

    Measured 2026-09-07: 322 serials repeat. 2017001103 carries a 살균 clause
    and a 멸균 clause for the same 세균수 (differ in `clause_seq` only), and
    2016003195/B90516 a sum rule beside its component (differ in
    `detail_item_name` only, the sum's being empty). Keyed on fewer columns
    the stage would keep one and drop the other silently.
    """
    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages(
                [
                    _record(),
                    _record(
                        clause_seq="2017000055",
                        clause_name="멸균제품에 한함",
                        standard_value="n=5, c=0, m=0",
                        judgment_format_code="04",
                        judgment_format_name="2군법",
                        microbe_2c="0",
                        microbe_2m="0",
                        microbe_3m="",
                    ),
                    _record(
                        individual_standard_seq="2016003195",
                        test_item_code="B90516",
                        detail_item_name="비스페놀A",
                        clause_seq="",
                        standard_value="0.6이하",
                    ),
                    _record(
                        individual_standard_seq="2016003195",
                        test_item_code="B90516",
                        detail_item_name="",
                        clause_seq="",
                        standard_value="2.5이하",
                    ),
                ]
            ),
            SYNCED_BY,
        ) == (4, 4)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerIndividualStandard)
        by_key = {
            (row.individual_standard_seq, row.detail_item_name, row.clause_seq): row.id
            for row in rows
        }
        assert sorted(by_key) == [
            ("2016003195", "", ""),
            ("2016003195", "비스페놀A", ""),
            ("2017001103", "세균수", "2017000055"),
            ("2017001103", "세균수", "2022000003"),
        ]

    # The empty key parts are "" and not NULL, so the next pass mints the same id.
    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages(
                [
                    _record(
                        individual_standard_seq="2016003195",
                        test_item_code="B90516",
                        detail_item_name="",
                        clause_seq="",
                        standard_value="2.5이하",
                    )
                ]
            ),
            SYNCED_BY,
            floor=0.0,
        ) == (1, 1)

    async with factory() as session:
        (row,) = await ledger_rows(session, FoodLedgerIndividualStandard)
        assert row.id == by_key[("2016003195", "", "")]


@pytest.mark.asyncio
async def test_individual_standard_ledger_skips_records_without_a_key(factory, pinned) -> None:
    """A record with no key cannot be matched again, so it must not be stored.

    The portal leaves columns empty on sparse rows (never the serial or the
    시험항목 on the measured feed); storing one would insert a duplicate on
    every later run and no query could ever find it. The other two key
    parts are allowed empty - that is their usual value.
    """
    async with pinned() as session:
        assert await _service(session).replace_individual_standard_ledger(
            pages(
                [
                    _record(),
                    _record(individual_standard_seq="   "),
                    _record(individual_standard_seq=None),
                    _record(test_item_code=""),
                    "not-a-record",
                ]
            ),
            SYNCED_BY,
        ) == (5, 1)

    async with factory() as session:
        assert len(await ledger_rows(session, FoodLedgerIndividualStandard)) == 1


@pytest.mark.asyncio
async def test_individual_standard_ledger_keeps_a_record_with_an_unreadable_timestamp(
    factory,
    pinned,
) -> None:
    """An unparseable 최종수정일시 costs that column, never the record."""
    async with pinned() as session:
        await _service(session).replace_individual_standard_ledger(
            pages([_record(last_updated_at="어제")]), SYNCED_BY
        )

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerIndividualStandard)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
