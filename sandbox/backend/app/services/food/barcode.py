# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.food import barcode as barcode_model
from app.models.food import ledger_health_functional_item_report as ledger_health_functional
from app.models.food import ledger_item_report
from app.models.food import ledger_livestock_item_report_raw_material as ledger_livestock
from app.models.food.barcode import FoodBarcode
from app.models.food.ledger_barcode import FoodLedgerBarcode
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 246,195 rows, 247 pages.
PAGE_SIZE = 1000

# Every column the model declares beyond its key and the audit trail - the
# ledger's own, one for one, so the two cannot drift apart.
SYNCED_COLUMNS = synced_columns(FoodBarcode, barcode_model.NATURAL_KEY)

# What the ledger answers, under the names this table gives them. C005 calls
# 화구 its date column `permit_date`; nothing here is a permit, and the
# column means 보고일자 as it does on `food_item_report` (rule://backend-ledger).
LEDGER_COLUMNS = {
    "report_date": "permit_date",
    "production_end_date": "production_end_date",
    "product_name": "product_name",
    "shelf_life": "shelf_life",
    "product_type_name": "product_type_name",
    "business_name": "business_name",
    "industry_name": "industry_name",
    "site_address": "site_address",
    "closed_business_date": "closed_business_date",
}

# The registries that number their reports, and the kind a number in each one
# belongs to. Import products are not here: their numbers are digests this
# repository computes, and C005 publishes none of them.
REGISTRIES = (
    (FoodLedgerItemReport, ledger_item_report.REPORT_KIND),
    (FoodLedgerLivestockItemReportRawMaterial, ledger_livestock.REPORT_KIND),
    (FoodLedgerHealthFunctionalItemReport, ledger_health_functional.REPORT_KIND),
)

# The registry left out, and why: 수입식품 numbers a product by a digest this
# codebase mints (`_import_product`), not by a 품목제조보고번호, so no published
# record can carry one and nothing would ever resolve against it.
UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "번호가 우리가 만드는 digest다"}


# ============================================================
# Classes
# ============================================================


class FoodBarcodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_barcode(self, synced_by: str) -> int:
        """Write `food_barcode` as a function of the C005 ledger; return its rows.

        The ledger whole - no filter: the derived table exists so that its edge
        to `food_item_report` can be declared on it and not on the ledger
        (rule://backend-relations). Two things are decided here rather than
        copied: the date column takes the name it means (보고일자), and
        `report_kind` is resolved by asking which registry numbers the report -
        C005 publishes a number and no registry, while the edge needs both.
        Read off the live ledger in keyed pages, staged, and written over in
        one short transaction (`LedgerStage.replace`, no floor: the ledger's
        own floor already vouched for the rows this reads).
        """
        stage = LedgerStage(self.session, FoodBarcode, barcode_model.NATURAL_KEY, SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                registry = await self._registry()
                async for page in scan_table(
                    self.session,
                    FoodLedgerBarcode,
                    barcode_model.NATURAL_KEY,
                    tuple(LEDGER_COLUMNS.values()),
                    PAGE_SIZE,
                ):
                    await stage.add([_barcode(record, registry) for record in page])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _registry(self) -> dict[str, str]:
        """Which registry each reported number belongs to - where the kind comes from.

        Read off the report ledgers rather than off `food_item_report`: a
        derivation is a function of the ledgers, and one that read another
        derived table would depend on the order `DERIVATIONS` writes them in
        (rule://backend-ledger). The three registries number in separate
        spaces, so a number has one answer or none.

        Held in memory - 1.9M short strings - because each of the 246,195
        barcodes asks the same question.
        """
        registry: dict[str, str] = {}
        for model, kind in REGISTRIES:
            rows = await self.session.execute(select(model.item_report_no))
            registry.update({number: kind for (number,) in rows.all()})
        return registry


# ============================================================
# Functions
# ============================================================


def _barcode(row: Mapping[str, object], registry: dict[str, str]) -> dict[str, object]:
    """One ledger row under this table's names, with the registry that numbered it."""
    number = row.get("item_report_no")
    return {
        "barcode_no": row.get("barcode_no"),
        "item_report_no": number,
        "report_kind": registry.get(str(number)),
        **{name: row.get(source) for name, source in LEDGER_COLUMNS.items()},
    }
