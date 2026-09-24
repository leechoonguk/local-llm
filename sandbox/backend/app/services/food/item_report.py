# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.ledger import LedgerStage, scan_table
from app.models.food import item_report as report
from app.models.food import ledger_import_food_label as ledger_import
from app.models.food.item_report import FoodItemReport
from app.models.food.ledger_health_functional_item_report import (
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_import_food_label import FoodLedgerImportFoodLabel
from app.models.food.ledger_item_report import FoodLedgerItemReport
from app.models.food.ledger_livestock_item_report_raw_material import (
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.repositories.food.common_standard_type import FoodCommonStandardTypeRepository
from app.repositories.food.item_report import FoodItemReportRepository
from app.repositories.food.label import FoodLabelRepository
from app.repositories.food.label_allergen import FoodLabelAllergenRepository
from app.repositories.food.label_caution import FoodLabelCautionRepository
from app.repositories.food.label_packaging import FoodLabelPackagingRepository
from app.repositories.food.product_classification import FoodProductClassificationRepository
from app.repositories.food.raw_material import FoodRawMaterialRepository
from app.repositories.food.standard import FoodStandardRepository
from app.schemas.food.item_report import FoodItemReportFacets, FoodItemReportFilter
from app.services.food.item_report_declaration import PRODUCT_KEY, PRODUCT_PREFIX, digest


if TYPE_CHECKING:
    from app.models.food.common_standard_type import FoodCommonStandardType
    from app.models.food.label import FoodLabel
    from app.models.food.label_allergen import FoodLabelAllergen
    from app.models.food.label_caution import FoodLabelCaution
    from app.models.food.label_packaging import FoodLabelPackaging
    from app.models.food.product_classification import FoodProductClassification
    from app.models.food.standard import (
        FoodStandard,  # read-side types only; the rebuild reads ledgers (rule://backend-ledger)
    )


# ============================================================
# Constants
# ============================================================

# The ledgers are read in pages of this many rows: 1,072,302 + 567,910, some
# 1,640 pages, each a keyed index walk.
PAGE_SIZE = 1000

# The key both ledgers carry a report under.
LEDGER_KEY = ("item_report_no",)

# What the import ledger is read in key order by, and the columns a product
# takes from it. 1,055,682 declarations collapse onto 292,867 products
# (2026-09-14), so the pass keeps, per product, the row with the newest
# 처리일자 - a product's representative declaration - and counts the rest as the
# declarations `food_item_report_declaration` holds.
IMPORT_LEDGER_KEY = ("importer_name", "product_name", "processed_date", "expiry_text")

# What a domestic registry's 제조국 is, stated once. Both I1250 and C006 publish
# only 국내 제조 products, so the column reads the same on every one of their
# 1,640,212 rows rather than being left for a reader to infer from the kind.
DOMESTIC_COUNTRY = "대한민국"

# What each ledger is read for, in the ledger's own words. The derived table's
# `SYNCED_COLUMNS` is what a row is written as, and since 2026-09-14 the two
# lists differ by name (`permit_date` -> `report_date`) and by the three
# columns only a derivation fills (`maker_name`, `origin_country`,
# `product_name_en`), so a pass names what it reads rather than assuming they
# are the same list.
DOMESTIC_LEDGER_COLUMNS = (
    "license_no",
    "business_name",
    "permit_date",
    "product_name",
    "product_type_name",
    "production_ended",
    "high_calorie_low_nutrition",
    "child_favorite_certified_yn",
    "shelf_life",
    "industry_name",
    "quality_maintenance_days",
    "usage_method",
    "purpose",
    "product_form",
    "packaging_material",
    "domestic_export_type",
    "source_updated_at",
)

# What the 건강기능식품 registry answers (I0030, 46,086 rows, 2026-09-15). Its
# names differ from the derived table's, so the slice maps them by hand.
HEALTH_FUNCTIONAL_LEDGER_COLUMNS = (
    "item_report_no",
    "product_name",
    "business_name",
    "license_no",
    "permit_date",
    "product_type_name",
    "product_form",
    "intake_method",
    "primary_functionality",
    "intake_caution",
    "storage_method",
    "standard_spec",
    "functional_indicator",
    "shelf_life",
    "packaging_material",
    "high_calorie_low_nutrition",
    "production_ended",
    "child_favorite_certified_yn",
    "industry_name",
)

# The six C006 answers of those.
LIVESTOCK_LEDGER_COLUMNS = (
    "license_no",
    "business_name",
    "permit_date",
    "product_name",
    "product_type_name",
    "source_updated_at",
)

IMPORT_COLUMNS = (
    *PRODUCT_KEY,
    "product_type_name",
    "processed_date",
    "declaration_kind",
)


# ============================================================
# Classes
# ============================================================


@dataclass(frozen=True)
class LabelPanel:
    """One printed label of a report: the label row, its allergens, cautions and packaging."""

    label: FoodLabel
    allergens: list[FoodLabelAllergen]
    cautions: list[FoodLabelCaution]
    packagings: list[FoodLabelPackaging]


@dataclass(frozen=True)
class InheritedCommonStandard:
    """One 제2 clause as it applies to a type: the clause, its node, its heading path."""

    standard: FoodStandard
    inherited_from: FoodProductClassification
    heading_path: list[FoodCommonStandardType]


@dataclass(frozen=True)
class TypeStandards:
    """What the 공전 says about one type a report names."""

    node: FoodProductClassification
    path: list[FoodProductClassification]
    individual_standards: list[FoodStandard]
    common_standards: list[InheritedCommonStandard]


class FoodItemReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.item_report_repository = FoodItemReportRepository(session)
        self.classification_repository = FoodProductClassificationRepository(session)
        self.standard_repository = FoodStandardRepository(session)
        self.common_standard_type_repository = FoodCommonStandardTypeRepository(session)
        self.raw_material_repository = FoodRawMaterialRepository(session)
        self.label_repository = FoodLabelRepository(session)
        self.label_allergen_repository = FoodLabelAllergenRepository(session)
        self.label_caution_repository = FoodLabelCautionRepository(session)
        self.label_packaging_repository = FoodLabelPackagingRepository(session)

    async def get_item_report(self, food_item_report_id: UUID) -> FoodItemReport:
        item_report = await self.item_report_repository.get(food_item_report_id)
        if item_report is None:
            raise NotFoundError(food_item_report_id)
        return item_report

    async def list_item_reports(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: FoodItemReportFilter | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> list[FoodItemReport]:
        return await self.item_report_repository.list(offset, limit, filters, sort, order)

    async def count_item_reports(self, filters: FoodItemReportFilter | None = None) -> int:
        return await self.item_report_repository.count(filters)

    async def list_item_report_facets(self) -> FoodItemReportFacets:
        """The values the 식품유형 select offers: the table's own, read now, not typed once."""
        return FoodItemReportFacets(
            product_type_name=await self.item_report_repository.distinct_values("product_type_name")
        )

    async def list_item_reports_by_raw_material(
        self, food_raw_material_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[FoodItemReport]:
        """A page of the products whose label names one material, once the material is found."""
        if await self.raw_material_repository.get(food_raw_material_id) is None:
            raise NotFoundError(food_raw_material_id)
        return await self.item_report_repository.list_by_raw_material(
            food_raw_material_id, offset, limit
        )

    async def count_item_reports_by_raw_material(self, food_raw_material_id: UUID) -> int:
        return await self.item_report_repository.count_by_raw_material(food_raw_material_id)

    async def get_item_report_standards(self, food_item_report_id: UUID) -> list[TypeStandards]:
        """What the 공전 says about the product: per type it names, its 제5 and 제2 clauses.

        A 개별기준규격 (제5) is written on the type itself. A 공통기준규격 (제2)
        applies to everything under the node it is written on, so the type
        inherits every ancestor's - 가공식품's 160 rows reach every processed
        food. Read in four queries whatever the report names: the path of every
        type at once, then the clauses of every node on every path, then the
        heading path of every clause's heading.

        The 공전's exemptions (`food_common_standard_exclusion`, I2610) are not
        applied here, on purpose: measured 2026-09-09, none of the 21 names a
        heading the current outline carries or a (heading, test item) pair any
        clause has, and the nodes they hang on are 원료 tiers and retired codes,
        never a type a report names. A branch no data reaches would be green
        on invented fixtures only; it returns with the 원료 standards read.
        """
        report = await self.get_item_report(food_item_report_id)
        type_codes = [node.product_code for node in report.product_classifications]
        paths = await self.classification_repository.list_ancestor_paths(type_codes)
        node_codes = sorted({node.product_code for path in paths.values() for node in path})
        individuals = await self.standard_repository.list_individual_by_product_codes(type_codes)
        commons = await self.standard_repository.list_common_by_product_codes(node_codes)
        headings = await self.common_standard_type_repository.list_heading_paths(
            sorted({_heading_code(standard) for standard in commons})
        )

        commons_by_node: dict[str, list[FoodStandard]] = {}
        for standard in commons:
            commons_by_node.setdefault(standard.product_code or "", []).append(standard)

        result: list[TypeStandards] = []
        for node in report.product_classifications:
            path = paths.get(node.product_code, [])
            inherited = [
                InheritedCommonStandard(
                    standard=standard,
                    inherited_from=step,
                    heading_path=headings.get(_heading_code(standard), []),
                )
                for step in path
                for standard in commons_by_node.get(step.product_code, [])
            ]
            result.append(
                TypeStandards(
                    node=node,
                    path=path,
                    individual_standards=[
                        s for s in individuals if s.product_code == node.product_code
                    ],
                    common_standards=inherited,
                )
            )
        return result

    async def get_item_report_labels(self, food_item_report_id: UUID) -> list[LabelPanel]:
        """What the packages say about the product: every printed label, whoever published it.

        Four queries whatever the report carries - the labels under its 번호,
        then the allergens, cautions and packaging parts of those labels at once.

        A report with no label answers an empty list, which is still the common
        case: the two feeds together cover 9,750 of the 1,640,212 reports
        (2026-09-13), where the 푸드QR 표시사항 feed alone covered 1,911.

        This is the **표시값** - what a manufacturer printed - beside the
        analysed values `nutritions` carries. The printed 영양표시 is not here:
        the panel was dropped from this axis on 2026-09-13 because
        `food_nutrition` answers the same question over 319,060 products.
        """
        report = await self.get_item_report(food_item_report_id)
        labels = await self.label_repository.list_by_item_report_no(report.item_report_no)
        keys = [(label.source, label.label_key) for label in labels]
        allergens = await self.label_allergen_repository.list_by_labels(keys)
        cautions = await self.label_caution_repository.list_by_labels(keys)
        packagings = await self.label_packaging_repository.list_by_labels(keys)
        return [
            LabelPanel(
                label=label,
                allergens=[row for row in allergens if _belongs(row, label)],
                cautions=[row for row in cautions if _belongs(row, label)],
                packagings=[row for row in packagings if _belongs(row, label)],
            )
            for label in labels
        ]

    async def rebuild_item_report(self, synced_by: str) -> int:
        """Write `food_item_report` as a function of the three report ledgers; return its rows.

        One reported product whichever registry reported it: every I1250 row
        under `food`, column for column, and every C006 row under `livestock`
        with the six columns that registry answers and the eleven it does not
        left NULL (`LIVESTOCK_LEDGER_COLUMNS`). Read off the live ledgers in keyed
        pages, staged, and written over whole in one short transaction
        (`LedgerStage.replace`, no floor: each ledger's own floor already
        vouched for its rows). Idempotent, so a rule that changes is a rebuild
        and not a walk of either feed.

        The third slice is `import`: 1,055,682 수입신고 collapsed onto 292,867
        products, each numbered by the digest of the five columns that identify
        it, and each carrying the fields of its newest declaration. Its 품목보고
        columns are NULL for the same reason the livestock ones are - the import
        registry does not publish them.
        """
        stage = LedgerStage(self.session, FoodItemReport, report.NATURAL_KEY, report.SYNCED_COLUMNS)
        async with self.session.begin():
            await stage.create()
        try:
            async with self.session.begin():
                async for page in scan_table(
                    self.session,
                    FoodLedgerItemReport,
                    LEDGER_KEY,
                    DOMESTIC_LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_report(row, report.DOMESTIC_KIND) for row in page])
                async for page in scan_table(
                    self.session,
                    FoodLedgerLivestockItemReportRawMaterial,
                    LEDGER_KEY,
                    LIVESTOCK_LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_report(row, report.LIVESTOCK_KIND) for row in page])
                async for page in scan_table(
                    self.session,
                    FoodLedgerHealthFunctionalItemReport,
                    LEDGER_KEY,
                    HEALTH_FUNCTIONAL_LEDGER_COLUMNS,
                    PAGE_SIZE,
                ):
                    await stage.add([_health_functional_report(row) for row in page])
                await stage.add(list((await self._import_products()).values()))
                return await stage.replace(synced_by, floor=None)
        finally:
            async with self.session.begin():
                await stage.drop()

    async def _import_products(self) -> dict[str, dict[str, object]]:
        """The import ledger's declarations collapsed onto products, newest 처리일자 winning.

        A product is the five columns `PRODUCT_KEY` names and its number is
        their digest, so the same product read from any of its 1,055,682
        declarations is the same row. What a declaration alone knows - the
        dates, the 수출국 - stays on `food_item_report_declaration`; what lands
        here is what the product is.

        Held in memory rather than grouped in SQL because the winner is decided
        per product and the loser is discarded: 292,867 products (2026-09-14) at
        eight short strings each.
        """
        products: dict[str, dict[str, object]] = {}
        async for page in scan_table(
            self.session,
            FoodLedgerImportFoodLabel,
            IMPORT_LEDGER_KEY,
            IMPORT_COLUMNS,
            PAGE_SIZE,
            where=FoodLedgerImportFoodLabel.declaration_kind.in_(
                ledger_import.PRODUCT_DECLARATION_KINDS
            ),
        ):
            for row in page:
                number = digest(PRODUCT_PREFIX, row, PRODUCT_KEY)
                held = products.get(number)
                processed = str(row.get("processed_date") or "")
                if held is not None and str(held["report_date"] or "") >= processed:
                    continue
                products[number] = _import_product(number, row)
        return products


# ============================================================
# Functions
# ============================================================


def _belongs(
    row: FoodLabelAllergen | FoodLabelCaution | FoodLabelPackaging, label: FoodLabel
) -> bool:
    """Whether a child row was printed on this label - the pair, never the key alone."""
    return row.source == label.source and row.label_key == label.label_key


def _import_product(number: str, row: Mapping[str, object]) -> dict[str, object]:
    """One import product: the five key columns under their digest, the rest NULL.

    `report_date` is the 처리일자 of the declaration this row was taken from -
    the newest one, which is what a product's 보고일자 means here - `business_name`
    is the 수입업체 that reported it and `maker_name` the 해외제조업소 that made
    it. The eleven domestic registry fields stay NULL, and so does `shelf_life`:
    this registry answers 유통기한 as a *range* between two dates ('20260807' ~
    '20270806') where the column holds the *period* a domestic report states
    ('제조일로부터 12개월'). Two facts, one name - so the range stays where it
    was declared, `food_item_report_declaration.expiry_from`/`expiry_to`.
    """
    return {
        "report_kind": report.IMPORT_KIND,
        "item_report_no": number,
        **{name: None for name in report.SYNCED_COLUMNS},
        "business_name": row.get("importer_name"),
        "maker_name": row.get("overseas_maker_name"),
        "origin_country": row.get("origin_country"),
        "product_name": row.get("product_name"),
        "product_name_en": row.get("product_name_en"),
        "product_type_name": row.get("product_type_name"),
        "report_date": row.get("processed_date"),
    }


def _health_functional_report(row: Mapping[str, object]) -> dict[str, object]:
    """One 건강기능식품 report as a product row - the same columns, its own words.

    The registry publishes four things nothing else does (주된기능성,
    섭취시주의사항, 보관방법, 기준규격) and calls 허가일자 what the others call
    품목제조보고일; the column means 보고일자 here as everywhere. 제조국 is
    `DOMESTIC_COUNTRY`: this registry reports 국내 제조 건강기능식품.
    """
    return {
        "report_kind": report.HEALTH_FUNCTIONAL_KIND,
        "item_report_no": row.get("item_report_no"),
        **{name: None for name in report.SYNCED_COLUMNS},
        "business_name": row.get("business_name"),
        "maker_name": row.get("business_name"),
        "origin_country": DOMESTIC_COUNTRY,
        "license_no": row.get("license_no"),
        "report_date": row.get("permit_date"),
        "product_name": row.get("product_name"),
        "product_type_name": row.get("product_type_name"),
        "product_form": row.get("product_form"),
        "usage_method": row.get("intake_method"),
        "packaging_material": row.get("packaging_material"),
        "shelf_life": row.get("shelf_life"),
        "industry_name": row.get("industry_name"),
        "production_ended": row.get("production_ended"),
        "high_calorie_low_nutrition": row.get("high_calorie_low_nutrition"),
        "child_favorite_certified_yn": row.get("child_favorite_certified_yn"),
        "primary_functionality": row.get("primary_functionality"),
        "intake_caution": row.get("intake_caution"),
        "storage_method": row.get("storage_method"),
        "standard_spec": row.get("standard_spec"),
        "functional_indicator": row.get("functional_indicator"),
    }


def _report(row: Mapping[str, object], kind: str) -> dict[str, object]:
    """The derived row: the ledger row under its registry's kind, every I1250 column present.

    `maker_name` and `origin_country` are filled, not left NULL: a domestic
    registry names one business, which both reported and made the product, and
    the country a 식품 was made in is a fact of the registry, not a
    guess. `product_name_en` stays NULL - neither registry publishes one.
    """
    return {
        "report_kind": kind,
        "item_report_no": row.get("item_report_no"),
        **{name: row.get(name) for name in report.SYNCED_COLUMNS},
        "report_date": row.get("permit_date"),
        "maker_name": row.get("business_name"),
        "origin_country": DOMESTIC_COUNTRY,
        "product_name_en": None,
    }


def _heading_code(standard: FoodStandard) -> str:
    """The 공전 heading a clause hangs on; a clause the portal left unheaded hangs on none."""
    return standard.common_standard_type_code or ""
