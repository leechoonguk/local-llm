"""FoodItemReportDeclarationService tests - one row per 수입신고, numbered by digest."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.food.item_report_declaration import FoodItemReportDeclaration
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_production import FoodLedgerProduction
from app.services.food.item_report_declaration import (
    PRODUCT_KEY,
    PRODUCT_PREFIX,
    FoodItemReportDeclarationService,
    digest,
)


SYNCED_BY = "batch:derive_food_tables"


def _ledger(**overrides: object) -> FoodLedgerImportFoodLabel:
    values: dict[str, object] = {
        "importer_name": "주식회사 쏠트코리아",
        "product_name": "천일염(식용)",
        "product_name_en": "SEA SALT",
        "product_type_name": "천일염",
        "overseas_maker_name": "UBAIDIA MINERALS",
        "origin_country": "파키스탄",
        "export_country": "파키스탄",
        "processed_date": "20200508",
        "expiry_text": "20180810 ~ 20280809",
        "declaration_kind": "가공식품",
        "created_by": "test",
        "updated_by": "test",
    }
    values.update(overrides)
    return FoodLedgerImportFoodLabel(**values)


@pytest.mark.asyncio
async def test_every_declaration_is_a_row_under_its_own_digest(factory, pinned) -> None:
    """Two declarations of one product are two rows pointing at one product number.

    The publisher states no key, so both numbers are digests of the record: the
    declaration's of the nine columns it is identified by, the product's of the
    five that identify what was declared.
    """
    async with factory() as session, session.begin():
        session.add_all([_ledger(), _ledger(processed_date="20260911")])

    async with pinned() as session:
        assert (
            await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(
                SYNCED_BY
            )
            == 2
        )

    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(FoodItemReportDeclaration).order_by(
                        FoodItemReportDeclaration.processed_date
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [row.report_kind for row in rows] == ["import", "import"]
        assert len({row.declaration_key for row in rows}) == 2
        assert len({row.item_report_no for row in rows}) == 1
        # The product's columns are not repeated on a declaration since
        # 2026-09-14, so the digest is checked against the ledger row it was
        # computed from - which is where a reader would recompute it.
        ledger = _ledger()
        assert rows[0].item_report_no == digest(
            PRODUCT_PREFIX,
            {name: getattr(ledger, name) for name in PRODUCT_KEY},
            PRODUCT_KEY,
        )


@pytest.mark.asyncio
async def test_a_rebuild_gives_a_declaration_the_same_number(factory, pinned) -> None:
    """The table is dropped and refilled every night; a number is a function of the record."""
    async with factory() as session, session.begin():
        session.add(_ledger())

    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)
    async with factory() as session:
        first = (await session.execute(select(FoodItemReportDeclaration))).scalar_one()
        before = (first.declaration_key, first.item_report_no, first.id)

    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)
    async with factory() as session:
        again = (await session.execute(select(FoodItemReportDeclaration))).scalar_one()
        assert (again.declaration_key, again.item_report_no, again.id) == before


@pytest.mark.asyncio
async def test_a_product_reads_its_declarations_newest_first(factory, pinned) -> None:
    """The read side of the table: one product's crossings, in the order a reader wants them.

    Paged, because the widest product carries 1,388 of them (2026-09-14), and
    keyed by the product's own pair rather than a row id - the screen has the
    product in hand when it asks.
    """
    async with factory() as session, session.begin():
        session.add_all(
            [
                _ledger(processed_date="20200508"),
                _ledger(processed_date="20260911"),
                _ledger(product_name="다른제품", processed_date="20250101"),
            ]
        )
    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)

    async with factory() as session:
        service = FoodItemReportDeclarationService(session)
        number = digest(
            PRODUCT_PREFIX,
            {name: getattr(_ledger(), name) for name in PRODUCT_KEY},
            PRODUCT_KEY,
        )
        assert await service.count_declarations("import", number) == 2
        rows = await service.list_declarations("import", number)
        assert [row.processed_date for row in rows] == ["20260911", "20200508"]
        assert [
            row.processed_date
            for row in await service.list_declarations("import", number, offset=1, limit=1)
        ] == ["20200508"]
        assert await service.count_declarations("domestic", number) == 0
        assert await service.list_declarations("domestic", number) == []


def _production_ledger(**overrides: object) -> FoodLedgerProduction:
    """One I0300 생산실적 row, as its ledger holds it."""
    record: dict[str, object] = {
        "item_report_no": "201202942713",
        "report_year": "2025",
        "product_name": "땅콩소스",
        "license_no": "20120294271",
        "production_qty": "760",
        "annual_capacity_qty": "1,000",
    }
    record.update(overrides)
    return FoodLedgerProduction(**record, created_by="test", updated_by="test")


@pytest.mark.asyncio
async def test_a_year_of_production_is_a_declaration_of_its_product(factory, pinned) -> None:
    """생산실적 lands in the declaration table, under the registry its number is in.

    The quantities are read out of the published strings - digits with at most
    one decimal point, thousands separators removed - and the import columns
    stay NULL, as the production columns do on an import declaration.
    """
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerItemReport(
                    item_report_no="201202942713", created_by="test", updated_by="test"
                ),
                _production_ledger(),
                _production_ledger(report_year="2024", production_qty="12.5"),
            ]
        )

    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodItemReportDeclaration))).scalars().all()
    assert sorted((row.report_kind, row.report_year, row.production_qty_kg) for row in rows) == [
        ("domestic", "2024", Decimal("12.500")),
        ("domestic", "2025", Decimal("760.000")),
    ]
    assert {row.declaration_kind for row in rows} == {"생산실적"}
    assert [row.annual_capacity_kg for row in rows] == [Decimal("1000.000"), Decimal("1000.000")]
    # An import declaration's columns are not a production row's.
    assert {row.processed_date for row in rows} == {None}
    assert {row.export_country for row in rows} == {None}


@pytest.mark.asyncio
async def test_production_of_a_product_no_registry_reports_is_dropped(factory, pinned) -> None:
    """A figure with no product to hang on is not a fact a screen can show."""
    async with factory() as session, session.begin():
        session.add(_production_ledger(item_report_no="999999999999"))

    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)

    async with factory() as session:
        assert (await session.execute(select(FoodItemReportDeclaration))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_quantity_no_number_can_be_read_from_is_left_empty(factory, pinned) -> None:
    """A range or a word is stored as NULL rather than guessed at, and counted."""
    async with factory() as session, session.begin():
        session.add_all(
            [
                FoodLedgerItemReport(
                    item_report_no="201202942713", created_by="test", updated_by="test"
                ),
                _production_ledger(production_qty="약 700", annual_capacity_qty="   "),
                _production_ledger(report_year="2024", production_qty=None),
            ]
        )

    async with pinned() as session:
        await FoodItemReportDeclarationService(session).rebuild_item_report_declaration(SYNCED_BY)

    async with factory() as session:
        rows = (await session.execute(select(FoodItemReportDeclaration))).scalars().all()
    row = next(row for row in rows if row.report_year == "2025")
    # A column the feed left empty is NULL here too, and is no failure.
    assert next(row for row in rows if row.report_year == "2024").production_qty_kg is None
    # The word is unreadable and counted; the blank string published nothing
    # and is not a failure - both end as NULL.
    assert row.production_qty_kg is None
    assert row.annual_capacity_kg is None
