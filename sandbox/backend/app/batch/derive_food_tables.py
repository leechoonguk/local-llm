# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import BatchSkippedError
from app.core.ledger import Derivation
from app.services.batch.run import BatchRunService, current_run_id, run_start_gate
from app.services.food.barcode import FoodBarcodeService
from app.services.food.business import FoodBusinessService
from app.services.food.common_standard_exclusion import FoodCommonStandardExclusionService
from app.services.food.common_standard_type import FoodCommonStandardTypeService
from app.services.food.item_report import FoodItemReportService
from app.services.food.item_report_declaration import FoodItemReportDeclarationService
from app.services.food.item_report_ingredient import FoodItemReportIngredientService
from app.services.food.label_family import FoodLabelFamilyService
from app.services.food.nutrition import FoodNutritionService
from app.services.food.product_classification import FoodProductClassificationService
from app.services.food.raw_material import FoodRawMaterialService
from app.services.food.safety_record import FoodSafetyRecordService
from app.services.food.standard import FoodStandardService
from app.services.food.test_item import FoodTestItemService


# ============================================================
# Constants
# ============================================================

logger = structlog.get_logger(__name__)

# Written into `created_by`/`updated_by`: an audit trail states who wrote a
# row, and for these rows the answer is this job, not a person.
SYNCED_BY = "batch:derive_food_tables"

# This job's own code, as the schedule and the run rows carry it: a second
# derivation in flight is as much a reason to stand down as a ledger job is -
# both mean these fifteen tables are being written by somebody else.
THIS_JOB = "derive_food_tables"

# The jobs whose ledgers the derived tables are read from. A derivation is a
# function of the ledgers as they stand, so it waits for their night to be
# over: one of these with an execution in flight means the ledgers are about
# to change, and a table rebuilt now would stand a day behind them.
DEPENDENCIES: tuple[str, ...] = (
    "sync_food_ledger_barcode",
    "sync_food_ledger_business",
    "sync_food_ledger_business_site",
    "sync_food_ledger_manufacturing_closure",
    "sync_food_ledger_additive_manufacturing_closure",
    "sync_food_ledger_import_business_closure",
    "sync_food_ledger_health_functional_closure",
    "sync_food_ledger_livestock_processing_closure",
    "sync_food_ledger_meat_packaging_closure",
    "sync_food_ledger_collection_inspection",
    "sync_food_ledger_common_standard",
    "sync_food_ledger_common_standard_exclusion",
    "sync_food_ledger_common_standard_type",
    "sync_food_ledger_haccp_label",
    "sync_food_ledger_health_functional_item_report",
    "sync_food_ledger_health_functional_production",
    "sync_food_ledger_import_food_label",
    "sync_food_ledger_individual_standard",
    "sync_food_ledger_inspection_failure",
    "sync_food_ledger_item_report",
    "sync_food_ledger_item_report_raw_material",
    "sync_food_ledger_livestock_item_report_raw_material",
    "sync_food_ledger_livestock_production",
    "sync_food_ledger_nutrition",
    "sync_food_ledger_product_classification",
    "sync_food_ledger_production",
    "sync_food_ledger_qr_allergy",
    "sync_food_ledger_qr_caution",
    "sync_food_ledger_qr_label",
    "sync_food_ledger_qr_manufacture",
    "sync_food_ledger_qr_nutrition",
    "sync_food_ledger_qr_packaging",
    "sync_food_ledger_qr_raw_material",
    "sync_food_ledger_qr_storage",
    "sync_food_ledger_raw_material",
    "sync_food_ledger_recall",
    "sync_food_ledger_test_item",
)


# Rebuilt in this order, each in its own short transaction. The order is the
# dependency between tables at read time - a reader of the graph after the run
# finds every edge's target rebuilt no later than its source - and not a
# dependency at write time: each one reads ledgers only.
DERIVATIONS: tuple[Derivation, ...] = (
    # The businesses first: a function of eight ledgers and nothing derived,
    # and the table the product registries will point at.
    Derivation(FoodBusinessService, FoodBusinessService.rebuild_business),
    Derivation(FoodTestItemService, FoodTestItemService.rebuild_test_item),
    Derivation(
        FoodCommonStandardTypeService, FoodCommonStandardTypeService.rebuild_common_standard_type
    ),
    Derivation(
        FoodProductClassificationService,
        FoodProductClassificationService.rebuild_product_classification,
    ),
    Derivation(FoodStandardService, FoodStandardService.rebuild_standard),
    Derivation(
        FoodCommonStandardExclusionService,
        FoodCommonStandardExclusionService.rebuild_common_standard_exclusion,
    ),
    Derivation(FoodRawMaterialService, FoodRawMaterialService.rebuild_raw_material),
    Derivation(FoodItemReportService, FoodItemReportService.rebuild_item_report),
    Derivation(
        FoodItemReportIngredientService,
        FoodItemReportIngredientService.rebuild_item_report_ingredient,
    ),
    Derivation(
        FoodSafetyRecordService,
        FoodSafetyRecordService.rebuild_safety_record,
    ),
    # After `food_item_report`, which its edge points at.
    Derivation(
        FoodItemReportDeclarationService,
        FoodItemReportDeclarationService.rebuild_item_report_declaration,
    ),
    Derivation(FoodNutritionService, FoodNutritionService.rebuild_nutrition),
    # After `food_item_report`, which its edge points at.
    Derivation(FoodBarcodeService, FoodBarcodeService.rebuild_barcode),
    # The label family - `food_label` and its three printed lists - written by
    # one derivation, after `food_item_report` because its edge points there.
    Derivation(FoodLabelFamilyService, FoodLabelFamilyService.rebuild_label_family),
)


# ============================================================
# Functions
# ============================================================


async def derive_food_tables() -> int:
    """Rebuild every derived food table off the ledgers, once the ledger jobs are done.

    The derived tables (the classification tree, the five 기준규격 tables, the
    raw materials, the reports and their ingredients) are functions of the
    ledgers the provider jobs fill, and nothing else writes them: each is
    read off its ledgers in keyed pages, staged, and written over whole
    (`LedgerStage.replace`, no floor). Rebuilding rather than maintaining
    means a rule that changes - which nodes are in the 공전, which classes are
    ingredients - is a run of this job, minutes off the live ledgers, and not
    a walk of the feeds, hours and quota.

    **It waits for the ledgers' night to be over.** A ledger job with an
    execution in flight (`list_running_codes`) is about to replace ledgers
    this job reads, so the run ends SKIPPED with the reason and writes
    nothing: the next fire rebuilds against the finished night. A second
    derivation in flight stands the new one down for the same reason - these
    tables have one writer. A feed that *failed* is not
    waited for - its ledger is last night's, whole, and the derivation is a
    function of whatever the ledgers hold.

    Returns the number of derived rows written, over every table.
    """
    # Read under the gate the scheduler opens run rows under: this reading and
    # every row written around it are then in one order, and a job that started
    # a millisecond earlier is seen rather than missed.
    async with run_start_gate():  # noqa: SIM117 — the gate orders the reading below
        async with AsyncSession(engine) as session:
            batch_run_service = BatchRunService(session)
            running = await batch_run_service.list_running_codes(excluding=current_run_id.get())
    blocking = sorted(running & (set(DEPENDENCIES) | {THIS_JOB}))
    if blocking:
        raise BatchSkippedError(f"still writing what this job reads: {', '.join(blocking)}")

    written = 0
    # Pinned to one connection: the stage each rebuild fills is a TEMP table,
    # and a TEMP table lives on the connection that created it.
    async with engine.connect() as connection, AsyncSession(connection) as session:
        for derivation in DERIVATIONS:
            written += await derivation.rebuild(derivation.service(session), SYNCED_BY)
    return written


if __name__ == "__main__":  # pragma: no cover — entry point, not testable logic
    total = asyncio.run(derive_food_tables())
    print(f"Wrote {total} derived rows")
