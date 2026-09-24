"""FoodLedgerLivestockProductionService tests — the ledger is the pass, year by year."""

import pytest
from sqlalchemy import select

from app.models.food.ledger_livestock_production import FoodLedgerLivestockProduction
from app.services.food.ledger_livestock_production import FoodLedgerLivestockProductionService


SYNCED_BY = "batch:sync_mfds_ledgers"


def _replace(session):
    """The one method that fills this ledger, named once for the tests below."""
    service = FoodLedgerLivestockProductionService(session)
    return service.replace_livestock_production_ledger


def _record(**overrides: object) -> dict[str, object]:
    """One canonical I1420 record, as the walk hands it over."""
    record: dict[str, object] = {
        "item_report_no": "201202942713",
        "report_year": "2025",
        "product_name": "땅콩소스",
        "license_no": "20120294271",
        "business_name": "가야푸드",
        "product_type_name": "소스류(조미식품)",
        "production_qty": "760",
        "annual_capacity_qty": "1000",
        "product_kind_name": "가공식품",
    }
    record.update(overrides)
    return record


async def _pages(*pages: list[dict[str, object]]):
    for page in pages:
        yield page


@pytest.mark.asyncio
async def test_the_ledger_is_every_year_the_walk_handed_over(factory, pinned) -> None:
    """The pages of several 보고년도 land in one stage and replace the ledger once.

    That is what makes a segmented walk a whole-feed ledger: the years are how
    the feed is addressed, so the ledger after the pass holds all of them.
    """
    async with pinned() as session:
        received, written = await _replace(session)(
            _pages(
                [
                    _record(report_year="2024"),
                    _record(report_year="2024", product_name="땅콩소스2"),
                ],
                [_record(report_year="2025")],
            ),
            SYNCED_BY,
            floor=None,
        )

    assert (received, written) == (3, 3)
    async with factory() as session:
        rows = (await session.execute(select(FoodLedgerLivestockProduction))).scalars().all()
    assert sorted((row.report_year, row.product_name) for row in rows) == [
        ("2024", "땅콩소스"),
        ("2024", "땅콩소스2"),
        ("2025", "땅콩소스"),
    ]
    assert {row.created_by for row in rows} == {SYNCED_BY}


@pytest.mark.asyncio
async def test_a_record_missing_a_key_part_cannot_be_matched_again(factory, pinned) -> None:
    """Four parts make the key; a record missing one is dropped where it arrives.

    Measured on the live feed (2026-09-15): 5 of 4,000 sampled I1420 rows
    carry no 품목제조보고번호.
    """
    async with pinned() as session:
        received, written = await _replace(session)(
            _pages([_record(item_report_no=None), _record()]),
            SYNCED_BY,
            floor=None,
        )

    assert (received, written) == (2, 1)
    async with factory() as session:
        rows = (await session.execute(select(FoodLedgerLivestockProduction))).scalars().all()
    assert [row.item_report_no for row in rows] == ["201202942713"]


@pytest.mark.asyncio
async def test_a_record_missing_its_name_or_licence_is_dropped_too(factory, pinned) -> None:
    """All four parts or none: two records share a number and a year otherwise."""
    async with pinned() as session:
        received, written = await _replace(session)(
            _pages([_record(product_name=None), _record(license_no=None), _record()]),
            SYNCED_BY,
            floor=None,
        )

    assert (received, written) == (3, 1)


@pytest.mark.asyncio
async def test_the_same_record_keeps_its_id_across_passes(factory, pinned) -> None:
    """A row's id is minted from its key, so a second pass rewrites the same row."""
    async with pinned() as session:
        await _replace(session)(_pages([_record()]), SYNCED_BY, floor=None)
    async with factory() as session:
        first = (await session.execute(select(FoodLedgerLivestockProduction))).scalar_one()
        first_id = first.id

    async with pinned() as session:
        await _replace(session)(_pages([_record(production_qty="900")]), SYNCED_BY, floor=None)
    async with factory() as session:
        second = (await session.execute(select(FoodLedgerLivestockProduction))).scalar_one()

    assert second.id == first_id
    assert second.production_qty == "900"
