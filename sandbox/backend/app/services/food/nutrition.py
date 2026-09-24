# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ledger import LedgerStage, scan_table, synced_columns
from app.models.food import ledger_health_functional_item_report as ledger_health_functional
from app.models.food import ledger_item_report, nutrition
from app.models.food import ledger_livestock_item_report_raw_material as ledger_livestock
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_nutrition import FoodLedgerNutrition
from app.models.food.nutrition import FoodNutrition


# ============================================================
# Constants
# ============================================================

# The ledger is read in pages of this many rows: 319,060 rows, 320 pages.
PAGE_SIZE = 1000

# Every column the model declares beyond its key and the audit trail - the
# ledger's own, one for one, so the two cannot drift apart.
SYNCED_COLUMNS = synced_columns(FoodNutrition, nutrition.NATURAL_KEY)

# What the ledger answers: every synced column but the one this job decides.
LEDGER_COLUMNS = tuple(name for name in SYNCED_COLUMNS if name != "report_kind")

# The registries that number their reports, and the kind a number in each one
# belongs to. Import products are not here: their numbers are digests this
# repository computes, and I2790 publishes none of them.
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


class FoodNutritionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_nutrition(self, synced_by: str) -> int:
        """Write `food_nutrition` as a function of the I2790 ledger; return its rows.

        The ledger whole - no filter, no computed column: the derived table
        exists so that its edges can be declared on it and not on the ledger
        (rule://backend-relations). Read off the live ledger in keyed pages,
        staged, and written over in one short transaction (`LedgerStage.replace`,
        no floor: the ledger's own floor already vouched for the rows this reads).
        """
        stage = LedgerStage(self.session, FoodNutrition, nutrition.NATURAL_KEY, SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                registry = await self._registry()
                async for page in scan_table(
                    self.session,
                    FoodLedgerNutrition,
                    nutrition.NATURAL_KEY,
                    LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_nutrition(record, registry) for record in page])
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _registry(self) -> dict[str, str]:
        """Which registry each reported number belongs to - where the kind comes from.

        Read off the report ledgers, not off `food_item_report`: a derivation is
        a function of the ledgers, and one that read another derived table would
        depend on the order `DERIVATIONS` writes them in (rule://backend-ledger).

        Held in memory - 1.9M short strings - because each of the 319,060
        records asks the same question, and 172,476 of them name a number.
        """
        registry: dict[str, str] = {}
        for model, kind in REGISTRIES:
            rows = await self.session.execute(select(model.item_report_no))
            registry.update({number: kind for (number,) in rows.all()})
        return registry


# ============================================================
# Functions
# ============================================================


def _nutrition(row: Mapping[str, object], registry: dict[str, str]) -> dict[str, object]:
    """One ledger row plus the registry that numbered the report it names."""
    number = row.get("item_report_no")
    return {
        **row,
        "report_kind": None if number is None else registry.get(str(number)),
    }
