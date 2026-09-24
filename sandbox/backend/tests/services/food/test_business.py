"""FoodBusinessService tests — the rebuild off the eight business ledgers."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.food.business import ACTIVE, CLOSED, FoodBusiness
from app.models.food.ledger_business import FoodLedgerBusiness
from app.models.food.ledger_business_site import FoodLedgerBusinessSite
from app.models.food.ledger_health_functional_closure import (
    FoodLedgerHealthFunctionalClosure,
)
from app.models.food.ledger_manufacturing_closure import FoodLedgerManufacturingClosure
from app.services.food.business import FoodBusinessService


SYNCED_BY = "batch:derive_food_tables"

MAKER = "식품제조가공업"

MAKER_MEAT = "식육포장처리업"


async def _rows(factory) -> dict[str, FoodBusiness]:
    async with factory() as session:
        result = await session.execute(select(FoodBusiness).order_by(FoodBusiness.license_no))
        return {row.license_no: row for row in result.scalars().all()}


@pytest.mark.asyncio
async def test_live_and_closed_rows_come_from_their_ledgers_and_a_rerun_replaces(
    factory, pinned
) -> None:
    """A master row is ACTIVE, a closure row is CLOSED with its closure columns.

    The rebuild is a function of the ledgers: run twice, the same rows.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerBusiness(
                    license_no="20060169056",
                    industry_name="식품제조가공업",
                    business_name="(New)금정상사",
                    permit_date="20061215",
                    district="대구광역시 북구",
                ),
                FoodLedgerManufacturingClosure(
                    license_no="18760461001",
                    industry_name="식품제조가공업",
                    business_name="(주)삼립웰가온양공장",
                    permit_date="19760521",
                    closed_date="20070130",
                    closure_kind="폐업(자진)",
                    district="충청남도 아산시",
                    institution_name="충청남도 아산시",
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        service = FoodBusinessService(session)
        assert await service.rebuild_business(SYNCED_BY) == 2
        assert await service.rebuild_business(SYNCED_BY) == 2

    rows = await _rows(factory)
    live, closed = rows["20060169056"], rows["18760461001"]
    assert (live.status, live.closed_date, live.closure_kind) == (ACTIVE, None, None)
    assert (closed.status, closed.closed_date, closed.closure_kind) == (
        CLOSED,
        "20070130",
        "폐업(자진)",
    )
    assert closed.institution_name == "충청남도 아산시"
    assert {row.created_by for row in rows.values()} == {SYNCED_BY}


@pytest.mark.asyncio
async def test_only_the_ten_industries_are_kept_from_either_side(factory, pinned) -> None:
    """A restaurant in the master and a 판매업 in a closure feed are not businesses here.

    Measured 2026-09-23: 52 industries in I2500, ten read; 302,242 of the
    302,735 건강기능식품 closures are 판매업.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerBusiness(license_no="1", industry_name="일반음식점", business_name="식"),
                FoodLedgerBusiness(
                    license_no="2", industry_name="건강기능식품전문제조업", business_name="제조"
                ),
                FoodLedgerHealthFunctionalClosure(
                    license_no="3", industry_name="건강기능식품일반판매업", business_name="판매"
                ),
                FoodLedgerHealthFunctionalClosure(
                    license_no="4", industry_name="건강기능식품벤처제조업", business_name="벤처"
                ),
            ]
        )
        await session.commit()

    async with pinned() as session:
        assert await FoodBusinessService(session).rebuild_business(SYNCED_BY) == 2

    rows = await _rows(factory)
    assert [(k, r.status) for k, r in rows.items()] == [("2", ACTIVE), ("4", CLOSED)]


@pytest.mark.asyncio
async def test_the_site_key_is_the_building_else_the_parcel_else_nothing(factory, pinned) -> None:
    """Two licences on one site share the key; a row the GIS ledger left bare has none.

    Measured 2026-09-23: 24.0 % of the GIS rows carry a building number,
    28.6 % a parcel code, the rest neither.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerBusiness(license_no="A", industry_name=MAKER, business_name="갑"),
                FoodLedgerBusiness(license_no="B", industry_name=MAKER_MEAT, business_name="갑"),
                FoodLedgerBusiness(license_no="C", industry_name=MAKER, business_name="을"),
                FoodLedgerBusiness(license_no="D", industry_name=MAKER, business_name="병"),
                FoodLedgerBusinessSite(license_no="A", building_no="BLD-1", parcel_code="PNU-1"),
                FoodLedgerBusinessSite(license_no="B", building_no="BLD-1", parcel_code="PNU-1"),
                FoodLedgerBusinessSite(license_no="C", building_no=None, parcel_code="PNU-2"),
                FoodLedgerBusinessSite(license_no="D", building_no=None, parcel_code=None),
            ]
        )
        await session.commit()

    async with pinned() as session:
        assert await FoodBusinessService(session).rebuild_business(SYNCED_BY) == 4

    rows = await _rows(factory)
    assert [rows[k].site_key for k in "ABCD"] == ["BLD-1", "BLD-1", "PNU-2", None]


@pytest.mark.asyncio
async def test_name_key_reads_one_name_through_its_corporate_spellings(factory, pinned) -> None:
    """The key the import ledger's importer_name is matched on: suffixes and spaces gone.

    `주식회사 오뚜기`, `(주)오뚜기` and `오뚜기㈜` are one name to a reader; a
    bracketed word that is not a suffix keeps its letters; an empty or absent name has no key.
    """
    spellings = {
        "1": "주식회사 오뚜기",
        "2": "(주)오뚜기",
        "3": "오뚜기㈜",
        "4": "농업회사법인 주식회사 제주우유",
        "5": "(New)금정상사",
        "6": "",
        "7": None,
    }
    async with factory() as session:
        session.add_all(
            [
                FoodLedgerBusiness(license_no=k, industry_name=MAKER, business_name=v)
                for k, v in spellings.items()
            ]
        )
        await session.commit()

    async with pinned() as session:
        assert await FoodBusinessService(session).rebuild_business(SYNCED_BY) == 7

    rows = await _rows(factory)
    assert [rows[k].name_key for k in "1234567"] == [
        "오뚜기",
        "오뚜기",
        "오뚜기",
        "농업회사법인제주우유",
        "New금정상사",
        None,
        None,
    ]


@pytest.mark.asyncio
async def test_reads_without_a_filter_count_everything_and_a_nameless_row_has_no_namesakes(
    factory,
) -> None:
    """A filterless count is the whole table; a nameless row has no namesakes.

    A row the portal named nothing has no name key, and asking for its
    namesakes answers an empty list rather than an error.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodBusiness(license_no="1", industry_name=MAKER, status=ACTIVE, name_key="갑"),
                FoodBusiness(license_no="2", industry_name=MAKER, status=CLOSED, name_key="갑"),
                FoodBusiness(license_no="3", industry_name=MAKER, status=ACTIVE, name_key=None),
            ]
        )
        await session.commit()

    async with factory() as session:
        service = FoodBusinessService(session)
        assert await service.count_businesses() == 3
        rows = {row.license_no: row for row in await service.list_businesses()}
        assert [b.license_no for b in await service.list_same_name(rows["1"])] == ["2"]
        assert await service.list_same_name(rows["3"]) == []


@pytest.mark.asyncio
async def test_one_business_reads_back_with_its_facets_and_its_neighbours(factory) -> None:
    """A row reads back by id, with the facets and the neighbours it has.

    The industry select offers the rows' own values; a site key finds the
    other licences on that site, and a row without one has none.
    """
    async with factory() as session:
        session.add_all(
            [
                FoodBusiness(license_no="1", industry_name=MAKER, status=ACTIVE, site_key="BLD-1"),
                FoodBusiness(
                    license_no="2", industry_name=MAKER_MEAT, status=ACTIVE, site_key="BLD-1"
                ),
                FoodBusiness(license_no="3", industry_name=MAKER, status=ACTIVE, site_key=None),
            ]
        )
        await session.commit()

    async with factory() as session:
        service = FoodBusinessService(session)
        rows = {row.license_no: row for row in await service.list_businesses()}
        found = await service.get_business(rows["1"].id)
        assert found.license_no == "1"
        with pytest.raises(NotFoundError):
            await service.get_business(uuid4())
        facets = await service.list_business_facets()
        assert facets.industry_name == [MAKER_MEAT, MAKER]
        assert [b.license_no for b in await service.list_same_site(found)] == ["2"]
        assert await service.list_same_site(rows["3"]) == []
