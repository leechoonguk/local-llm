# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from hashlib import sha256

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table
from app.models.food import item_report_declaration as declaration_model
from app.models.food import ledger_import_food_label as ledger_import
from app.models.food.item_report_declaration import FoodItemReportDeclaration
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_health_functional_production import (
    FoodLedgerHealthFunctionalProduction,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_livestock_production import FoodLedgerLivestockProduction
from app.models.food.ledger_production import FoodLedgerProduction
from app.repositories.food.item_report_declaration import FoodItemReportDeclarationRepository


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)

# The ledger is read in pages of this many rows: 1,055,682 rows is some 1,056
# pages, each a keyed index walk.
PAGE_SIZE = 1000

# What the publisher identifies nothing by, so the derivation does. The nine
# columns are the ledger's natural key - every column it answers except the two
# texts - and the five are what identifies the **product** under them:
# measured 2026-09-14 over the whole ledger, 수입업체+제품명 leave 229,681
# distinct, +영문명 261,246, +해외제조업소 291,542 and +제조국 292,867. The last
# is the key: the same 제품명 from another 해외제조업소 is another product, and
# the two columns cost 63,186 conflations if dropped.
PRODUCT_KEY = (
    "importer_name",
    "product_name",
    "product_name_en",
    "overseas_maker_name",
    "origin_country",
)
DECLARATION_KEY = (
    *PRODUCT_KEY,
    "export_country",
    "processed_date",
    "expiry_text",
    "product_type_name",
)

# The digest's prefix per scope, so a number says what it numbers on sight, and
# its width: 16 hex characters is 64 bits, which over 292,867 products is a
# birthday collision probability under 1e-9.
PRODUCT_PREFIX = "I"
DECLARATION_PREFIX = "D"
DIGEST_WIDTH = 16

# The separator the parts are joined with before hashing: U+001F, which no
# publisher writes, so `("A\u001fB", "C")` and `("A", "B\u001fC")` cannot
# collide by concatenation.
DIGEST_SEPARATOR = "\u001f"

# The ledger columns the derivation reads. The two texts are the label's, not a
# declaration's (`services/food/label.py`).
LEDGER_COLUMNS = (
    *DECLARATION_KEY,
    "declaration_kind",
    "expiry_from",
    "expiry_to",
)
LEDGER_KEY = ("importer_name", "product_name", "processed_date", "expiry_text")

# The three 생산실적 ledgers, the registry each one's numbers belong to, and the
# ledger whose numbers say a product is still reported. A figure whose
# 품목제조보고번호 is in no registry is dropped: a production quantity with no
# product to hang on is not something a screen can show.
PRODUCTION_SOURCES = (
    (
        FoodLedgerProduction,
        declaration_model.DOMESTIC_KIND,
        FoodLedgerItemReport,
    ),
    (
        FoodLedgerLivestockProduction,
        declaration_model.LIVESTOCK_KIND,
        FoodLedgerLivestockItemReportRawMaterial,
    ),
    (
        FoodLedgerHealthFunctionalProduction,
        declaration_model.HEALTH_FUNCTIONAL_KIND,
        FoodLedgerHealthFunctionalItemReport,
    ),
)

# What a 생산실적 row is keyed by within its registry: the feed, the product and
# the year. 품목명 is part of it because one number reports several 품목명 in
# one year (15 of 4,000 sampled I0300 rows, 2026-09-15) and each is its own
# declared figure.
PRODUCTION_KEY = ("item_report_no", "report_year", "product_name", "license_no")
PRODUCTION_LEDGER_KEY = ("item_report_no", "report_year", "product_name", "license_no")
PRODUCTION_COLUMNS = (
    *PRODUCTION_KEY,
    "production_qty",
    "annual_capacity_qty",
)

# 생산량/연간생산능력 arrive as digit strings and become numbers here. What is
# accepted: digits with at most one decimal point, after thousands separators
# and surrounding spaces are removed. Anything else - a range, a word, a unit -
# is stored as NULL rather than guessed at, and the rebuild counts those rows
# in its log line (`batch.derive.production_unparsed`).
_QUANTITY_STRIP = re.compile(r"[,\s]")
_QUANTITY = re.compile(r"^\d+(\.\d+)?$")


# ============================================================
# Classes
# ============================================================


class FoodItemReportDeclarationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.declaration_repository = FoodItemReportDeclarationRepository(session)

    async def list_declarations(
        self, report_kind: str, item_report_no: str, offset: int = 0, limit: int = 100
    ) -> Sequence[FoodItemReportDeclaration]:
        """One product's declarations, newest 처리일자 first.

        Keyed by the product's own key rather than by a row id: the caller has
        the product in hand, and this table hangs off that pair.
        """
        return await self.declaration_repository.list_by_report(
            report_kind, item_report_no, offset, limit
        )

    async def count_declarations(self, report_kind: str, item_report_no: str) -> int:
        """How many times the product was declared - 0 on a domestic product, which is the truth.

        The 품목제조보고 registries publish no declarations; the table is keyed by
        `report_kind` so they can be added without a rebuild, and until they
        are, a domestic product has none.
        """
        return await self.declaration_repository.count_by_report(report_kind, item_report_no)

    async def rebuild_item_report_declaration(self, synced_by: str) -> int:
        """Write `food_item_report_declaration` off the four ledgers; return its rows.

        Two kinds of declaration land in one table:

        - **수입신고**, one row per declaration of the import label ledger -
          1,055,682 of them (2026-09-14) - numbered by the digest of the nine
          columns the publisher identifies it by.
        - **생산실적**, one row per (product, 보고년도, 품목명) of the three
          production ledgers, numbered by the digest of the feed's own key. A
          row whose 품목제조보고번호 is in no report ledger is dropped.

        Every number is a function of the record, so the table can be dropped
        and rebuilt and a declaration keeps its number.

        Read off the live ledgers in keyed pages, staged, and written over in
        one short transaction (`LedgerStage.replace`, no floor: each ledger's
        own floor already vouched for its rows).
        """
        stage = LedgerStage(
            self.session,
            FoodItemReportDeclaration,
            declaration_model.NATURAL_KEY,
            declaration_model.SYNCED_COLUMNS,
        )
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session,
                    FoodLedgerImportFoodLabel,
                    LEDGER_KEY,
                    LEDGER_COLUMNS,
                    PAGE_SIZE,
                    where=FoodLedgerImportFoodLabel.declaration_kind.in_(
                        ledger_import.PRODUCT_DECLARATION_KINDS
                    ),
                ):
                    await stage.add([_declaration(row) for row in page])
                unparsed = await self._add_production(stage)
                written = await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()
        logger.info("batch.derive.production_unparsed", rows=unparsed)
        return written

    async def _add_production(self, stage: LedgerStage) -> int:
        """Stage every 생산실적 figure that hangs on a reported product; count the unreadable.

        The registry of each feed is read off the *report* ledger of its own
        kind rather than off `food_item_report`: a derivation is a function of
        the ledgers, and one reading another derived table would depend on the
        order `DERIVATIONS` writes them in (rule://backend-ledger).
        """
        unparsed = 0
        for ledger, kind, registry_model in PRODUCTION_SOURCES:
            rows = await self.session.execute(select(registry_model.item_report_no))
            reported = {number for (number,) in rows.all()}
            async for page in scan_table(
                self.session, ledger, PRODUCTION_LEDGER_KEY, PRODUCTION_COLUMNS, PAGE_SIZE
            ):
                staged = []
                for row in page:
                    if str(row.get("item_report_no")) not in reported:
                        continue
                    declaration, failures = _production(row, kind)
                    unparsed += failures
                    staged.append(declaration)
                await stage.add(staged)
        return unparsed


# ============================================================
# Functions
# ============================================================


def digest(prefix: str, row: Mapping[str, object], columns: Sequence[str]) -> str:
    """The deterministic number of a record: `<prefix><16 hex>` over the named columns.

    Shared by every derivation that numbers an import record, so a product read
    from the declaration table and the same product read from the report table
    are the same string. An absent column hashes as the empty string, which is
    what the publisher sent.
    """
    joined = DIGEST_SEPARATOR.join(str(row.get(name) or "") for name in columns)
    return prefix + sha256(joined.encode("utf-8")).hexdigest()[:DIGEST_WIDTH]


def _declaration(row: Mapping[str, object]) -> dict[str, object]:
    """One ledger row as a declaration, under its own digest and its product's."""
    return {
        "report_kind": declaration_model.IMPORT_KIND,
        "declaration_key": digest(DECLARATION_PREFIX, row, DECLARATION_KEY),
        "item_report_no": digest(PRODUCT_PREFIX, row, PRODUCT_KEY),
        **{
            name: row.get(name)
            for name in declaration_model.SYNCED_COLUMNS
            if name != "item_report_no"
        },
    }


def _production(row: Mapping[str, object], report_kind: str) -> tuple[dict[str, object], int]:
    """One 생산실적 ledger row as a declaration, and how many of its two figures were unreadable."""
    production, production_failed = _quantity(row.get("production_qty"))
    capacity, capacity_failed = _quantity(row.get("annual_capacity_qty"))
    return (
        {
            "report_kind": report_kind,
            "declaration_key": digest(DECLARATION_PREFIX, row, PRODUCTION_KEY),
            "item_report_no": str(row.get("item_report_no")),
            "declaration_kind": declaration_model.PRODUCTION_DECLARATION_KIND,
            "export_country": None,
            "processed_date": None,
            "expiry_from": None,
            "expiry_to": None,
            "report_year": row.get("report_year"),
            "production_qty_kg": production,
            "annual_capacity_kg": capacity,
        },
        production_failed + capacity_failed,
    )


def _quantity(value: object) -> tuple[Decimal | None, int]:
    """A published quantity as a number, or None and a count of one."""
    if not isinstance(value, str):
        return None, 0
    cleaned = _QUANTITY_STRIP.sub("", value)
    if not cleaned:
        return None, 0
    if not _QUANTITY.match(cleaned):
        return None, 1
    try:
        return Decimal(cleaned), 0
    except InvalidOperation:  # pragma: no cover - the pattern already refused it
        return None, 1
