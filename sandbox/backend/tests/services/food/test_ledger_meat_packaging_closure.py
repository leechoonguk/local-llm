"""FoodLedgerMeatPackagingClosureService tests — the ledger is the pass."""

import pytest
from sqlalchemy import select

from app.models.food.ledger_meat_packaging_closure import (
    FoodLedgerMeatPackagingClosure,
)
from app.services.food.ledger_meat_packaging_closure import (
    FoodLedgerMeatPackagingClosureService,
)


SYNCED_BY = "batch:sync_food_ledger_meat_packaging_closure"

FIRST = "19690137004"

SECOND = "19690137009"


def _replace(session):
    """The one method that fills this ledger, named once for the tests below."""
    service = FoodLedgerMeatPackagingClosureService(session)
    return service.replace_meat_packaging_closure_ledger


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I2825 record - the file's first row of 2026-09-23."""
    record: dict[str, object] = {
        "license_no": "19690137004",
        "business_name": "동해식품",
        "industry_name": "식육포장처리업",
        "permit_date": "19690708",
        "closed_date": "20180308",
        "closure_kind": "폐업(말소)",
        "district": "부산광역시 남구",
        "institution_name": "부산광역시 남구",
    }
    record.update(overrides)
    return record


async def _pages(*pages: list[dict[str, object]]):
    for page in pages:
        yield page


async def _by_licence(factory) -> dict[str, tuple[object, str | None, str | None]]:
    async with factory() as session:
        result = await session.execute(select(FoodLedgerMeatPackagingClosure))
        rows = result.scalars().all()
    return {r.license_no: (r.id, r.business_name, r.created_by) for r in rows}


@pytest.mark.asyncio
async def test_the_ledger_is_the_pass_and_a_rerun_keeps_the_ids(factory, pinned) -> None:
    """Every record of the pass is a row; a second pass rewrites the same rows.

    A row's id is minted from its 인허가번호, so a value that changed between
    passes lands on the same row and nothing joined to it moves.
    """
    async with pinned() as session:
        received, written = await _replace(session)(
            _pages([_record(), _record(license_no=SECOND, business_name="동해식품2")]),
            SYNCED_BY,
            floor=None,
        )
    assert (received, written) == (2, 2)
    first = await _by_licence(factory)

    async with pinned() as session:
        received, written = await _replace(session)(
            _pages(
                [
                    _record(business_name="바뀐 이름"),
                    _record(license_no=SECOND, business_name="동해식품2"),
                ]
            ),
            SYNCED_BY,
            floor=None,
        )
    assert (received, written) == (2, 2)
    second = await _by_licence(factory)

    assert second[FIRST] == (first[FIRST][0], "바뀐 이름", SYNCED_BY)
    assert second[SECOND] == first[SECOND]


@pytest.mark.asyncio
async def test_a_keyless_record_is_dropped_and_a_repeat_counts_once(factory, pinned) -> None:
    """The 인허가번호 is the key.

    A record without one cannot be matched again, and a number the file
    carries twice is one row - the first reading (the file of 2026-09-23
    carries such pairs where a district was renamed).
    """
    async with pinned() as session:
        received, written = await _replace(session)(
            _pages([_record(license_no=None), _record(), _record(district="다른 구")]),
            SYNCED_BY,
            floor=None,
        )
    assert (received, written) == (3, 1)
    rows = await _by_licence(factory)
    assert list(rows) == [FIRST]
