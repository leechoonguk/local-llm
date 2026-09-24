"""FoodLedgerProductClassificationService tests — CRUD and the ledger upsert the batch runs."""

import pytest

from app.models.food.ledger_product_classification import FoodLedgerProductClassification
from app.services.food.ledger_product_classification import FoodLedgerProductClassificationService
from tests.services.food.helpers import ledger_rows, pages


PRODUCT_CODE = "A0100000000000"

SYNCED_BY = "batch:sync_mfds_ledgers"


def _service(session) -> FoodLedgerProductClassificationService:
    return FoodLedgerProductClassificationService(session)


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
async def test_product_classification_ledger_after_a_second_pass_is_the_second_pass(
    factory,
    pinned,
) -> None:
    """A re-sent row is written again, under the id its key mints.

    Every night writes the whole feed over the ledger, so the second pass
    counts its row as written like the first; what a reader may hold on to
    is the `id`, which comes from the natural key and not from the night.
    """
    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        (first,) = await ledger_rows(session, FoodLedgerProductClassification)

    async with pinned() as session:
        assert await _service(session).replace_product_classification_ledger(
            pages([_record()]), SYNCED_BY
        ) == (1, 1)

    async with factory() as session:
        rows = await ledger_rows(session, FoodLedgerProductClassification)
        assert len(rows) == 1
        assert rows[0].id == first.id
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
        rows = await ledger_rows(session, FoodLedgerProductClassification)
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
        assert len(await ledger_rows(session, FoodLedgerProductClassification)) == 1


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
        rows = await ledger_rows(session, FoodLedgerProductClassification)
        assert len(rows) == 1
        assert rows[0].source_updated_at is None
