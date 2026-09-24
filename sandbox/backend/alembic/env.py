import asyncio
from logging.config import fileConfig

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool
from sqlalchemy.types import JSON

from alembic import context
from app.core.settings import settings
from app.models.base import Base
from app.models.batch.run import BatchRun  # noqa: F401 — on metadata
from app.models.batch.schedule import BatchSchedule  # noqa: F401 — on metadata
from app.models.batch.step import BatchStep  # noqa: F401 — on metadata
from app.models.food.barcode import FoodBarcode  # noqa: F401 — on metadata
from app.models.food.business import FoodBusiness  # noqa: F401 — on metadata
from app.models.food.common_standard_exclusion import (  # noqa: F401 — on metadata
    FoodCommonStandardExclusion,
)
from app.models.food.common_standard_type import FoodCommonStandardType  # noqa: F401 — on metadata
from app.models.food.item_report import FoodItemReport  # noqa: F401 — on metadata
from app.models.food.item_report_declaration import (  # noqa: F401 — on metadata
    FoodItemReportDeclaration,
)
from app.models.food.item_report_ingredient import (  # noqa: F401 — on metadata
    FoodItemReportIngredient,
)
from app.models.food.label import FoodLabel  # noqa: F401 — on metadata
from app.models.food.label_allergen import FoodLabelAllergen  # noqa: F401 — on metadata
from app.models.food.label_caution import FoodLabelCaution  # noqa: F401 — on metadata
from app.models.food.label_packaging import FoodLabelPackaging  # noqa: F401 — on metadata
from app.models.food.ledger_additive_manufacturing_closure import (  # noqa: F401 — on metadata
    FoodLedgerAdditiveManufacturingClosure,
)
from app.models.food.ledger_admin_disposition import (  # noqa: F401 — on metadata
    FoodLedgerAdminDisposition,
)
from app.models.food.ledger_barcode import FoodLedgerBarcode  # noqa: F401 — on metadata
from app.models.food.ledger_business import (  # noqa: F401 — on metadata
    FoodLedgerBusiness,
)
from app.models.food.ledger_business_site import (  # noqa: F401 — on metadata
    FoodLedgerBusinessSite,
)
from app.models.food.ledger_collection_inspection import (  # noqa: F401 — on metadata
    FoodLedgerCollectionInspection,
)
from app.models.food.ledger_common_standard import (  # noqa: F401 — on metadata
    FoodLedgerCommonStandard,
)
from app.models.food.ledger_common_standard_exclusion import (  # noqa: F401 — on metadata
    FoodLedgerCommonStandardExclusion,
)
from app.models.food.ledger_common_standard_type import (  # noqa: F401 — on metadata
    FoodLedgerCommonStandardType,
)
from app.models.food.ledger_haccp_label import FoodLedgerHaccpLabel  # noqa: F401 — on metadata
from app.models.food.ledger_health_functional_closure import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalClosure,
)
from app.models.food.ledger_health_functional_item_report import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_health_functional_production import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalProduction,
)
from app.models.food.ledger_import_business_closure import (  # noqa: F401 — on metadata
    FoodLedgerImportBusinessClosure,
)
from app.models.food.ledger_import_food_label import (  # noqa: F401 — on metadata
    FoodLedgerImportFoodLabel,
)
from app.models.food.ledger_individual_standard import (  # noqa: F401 — on metadata
    FoodLedgerIndividualStandard,
)
from app.models.food.ledger_inspection_failure import (  # noqa: F401 — on metadata
    FoodLedgerInspectionFailure,
)
from app.models.food.ledger_item_report import FoodLedgerItemReport  # noqa: F401 — on metadata
from app.models.food.ledger_item_report_raw_material import (  # noqa: F401 — on metadata
    FoodLedgerItemReportRawMaterial,
)
from app.models.food.ledger_livestock_item_report_raw_material import (  # noqa: F401 — on metadata
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_livestock_processing_closure import (  # noqa: F401 — on metadata
    FoodLedgerLivestockProcessingClosure,
)
from app.models.food.ledger_livestock_production import (  # noqa: F401 — on metadata
    FoodLedgerLivestockProduction,
)
from app.models.food.ledger_manufacturing_closure import (  # noqa: F401 — on metadata
    FoodLedgerManufacturingClosure,
)
from app.models.food.ledger_meat_packaging_closure import (  # noqa: F401 — on metadata
    FoodLedgerMeatPackagingClosure,
)
from app.models.food.ledger_nutrition import FoodLedgerNutrition  # noqa: F401 — on metadata
from app.models.food.ledger_product_classification import (  # noqa: F401 — on metadata
    FoodLedgerProductClassification,
)
from app.models.food.ledger_production import FoodLedgerProduction  # noqa: F401 — on metadata
from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy  # noqa: F401 — on metadata
from app.models.food.ledger_qr_caution import FoodLedgerQrCaution  # noqa: F401 — on metadata
from app.models.food.ledger_qr_label import FoodLedgerQrLabel  # noqa: F401 — on metadata
from app.models.food.ledger_qr_manufacture import (
    FoodLedgerQrManufacture,  # noqa: F401 — on metadata
)
from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition  # noqa: F401 — on metadata
from app.models.food.ledger_qr_packaging import FoodLedgerQrPackaging  # noqa: F401 — on metadata
from app.models.food.ledger_qr_raw_material import (
    FoodLedgerQrRawMaterial,  # noqa: F401 — on metadata
)
from app.models.food.ledger_qr_storage import FoodLedgerQrStorage  # noqa: F401 — on metadata
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial  # noqa: F401 — on metadata
from app.models.food.ledger_recall import FoodLedgerRecall  # noqa: F401 — on metadata
from app.models.food.ledger_test_item import FoodLedgerTestItem  # noqa: F401 — on metadata
from app.models.food.nutrition import FoodNutrition  # noqa: F401 — on metadata
from app.models.food.product_classification import (  # noqa: F401 — on metadata
    FoodProductClassification,
)
from app.models.food.raw_material import FoodRawMaterial  # noqa: F401 — on metadata
from app.models.food.safety_record import FoodSafetyRecord  # noqa: F401 — on metadata
from app.models.food.standard import FoodStandard  # noqa: F401 — on metadata
from app.models.food.test_item import FoodTestItem  # noqa: F401 — on metadata
from app.models.integration.call import IntegrationCall  # noqa: F401 — on metadata
from app.models.integration.field import IntegrationField  # noqa: F401 — on metadata
from app.models.integration.operation import IntegrationOperation  # noqa: F401 — on metadata
from app.models.integration.provider import Integration  # noqa: F401 — on metadata
from app.models.integration.secret import IntegrationSecret  # noqa: F401 — on metadata
from app.models.refresh import Refresh  # noqa: F401 — on metadata
from app.models.user import User  # noqa: F401 — on metadata


config = context.config

# Use DATABASE_URL from Settings/env, not alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _compare_server_default(
    context: object,
    inspected_column: object,
    metadata_column: Column[object],
    inspected_default: object,
    metadata_default: object,
    rendered_metadata_default: object,
) -> bool | None:
    """Whether a server default differs, with the one type Postgres cannot answer for.

    `compare_server_default` asks the database `SELECT <inspected> = <rendered>`,
    and for a JSON column that is `'{}'::json = '{}'`, which Postgres refuses:
    there is no equality operator for `json`. Measured 2026-09-16: turning the
    comparison on made `alembic check` raise UndefinedFunctionError, and the hook
    reported the database unreachable - a gate that compares nothing.

    A JSON default is declared once and never edited (the wire payload shapes),
    so it is read as unchanged; every other column goes through the normal
    comparison, which is what this was turned on for.
    """
    if isinstance(metadata_column.type, (JSON, JSONB)):
        return False
    return None


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async def _run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(_run())


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    # One transaction per migration, not one for the whole run. A multi-step run
    # that fails then stops at the last revision that fully applied, so the
    # version pointer and the rows still agree.
    #
    # Measured the other way round: a `downgrade base` that failed part-way left a
    # database whose pointer said 65 while an operation row from revision 66 was
    # still there, and the next `upgrade head` died on
    # `uq_integration_operation_provider_code`. Half an hour then went into
    # diagnosing a migration ordering defect that does not exist - the chain
    # downgrades cleanly from a consistent database.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
        # A column's server default is part of the schema, and autogenerate
        # ignores it unless asked. Measured 2026-09-16: three ledgers were
        # written without `version`'s default, `alembic check` reported in sync
        # for weeks, and the first pass that filled one of them died on the
        # NOT NULL constraint after walking its whole feed.
        compare_server_default=_compare_server_default,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
