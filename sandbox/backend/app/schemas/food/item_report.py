# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ============================================================
# Constants
# ============================================================

# Which registry reported the product - the two the model's CHECK admits
# (`models/food/item_report.KINDS`), spelled here so a reader can switch on it.
ReportKind = Literal["domestic", "livestock", "import", "health_functional"]

# What a supervising authority did about a product - the model's own CHECK
# (`models/food/item_report_event.EVENT_KINDS`), spelled here so a reader can
# switch on it.
RecordKind = Literal["recall", "inspection_failure", "collection_inspection"]

# Our reading of 판정결과 - the model's own CHECK
# (`models/food/safety_record.JUDGMENT_CODES`). The portal's word is data and
# travels as `judgment`; this is what a filter, a count and a colour use.
JudgmentCode = Literal["failed", "passed", "pending"]


# ============================================================
# Classes
# ============================================================


class FoodItemReportBase(BaseModel):
    """One reported product as the derived table holds it - both registries, one shape.

    Read-only over HTTP: the table is rebuilt whole by the derive job every
    night (rule://backend-ledger), so there is no Create or Update request -
    a row written by hand would be gone by morning.
    """

    model_config = ConfigDict(extra="forbid")

    report_kind: ReportKind
    item_report_no: str
    license_no: str | None = None
    business_name: str | None = None
    maker_name: str | None = None
    origin_country: str | None = None
    report_date: str | None = None
    product_name: str | None = None
    product_name_en: str | None = None
    primary_functionality: str | None = None
    intake_caution: str | None = None
    storage_method: str | None = None
    standard_spec: str | None = None
    functional_indicator: str | None = None
    product_type_name: str | None = None
    production_ended: str | None = None
    high_calorie_low_nutrition: str | None = None
    child_favorite_certified_yn: str | None = None
    shelf_life: str | None = None
    industry_name: str | None = None
    quality_maintenance_days: str | None = None
    usage_method: str | None = None
    purpose: str | None = None
    product_form: str | None = None
    packaging_material: str | None = None
    domestic_export_type: str | None = None
    source_updated_at: datetime | None = None


class FoodItemReportReadResponse(FoodItemReportBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class FoodItemReportClassificationReadResponse(BaseModel):
    """The 공전 type a report names - the node, not the whole tree row."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int

    product_code: str
    korean_name: str | None = None
    level: str | None = None
    root_product_code: str | None = None


class FoodItemReportIngredientReadResponse(BaseModel):
    """One ingredient of the report, in the order the label lists them."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int

    position: int
    ordinal: int | None = None
    name: str
    # Which of a registry's lists the name came from (기능성 / 기타 / 캡슐), and
    # null where the registry publishes one list.
    ingredient_role: str | None = None


class FoodItemReportNutritionReadResponse(BaseModel):
    """The nutrition record that names this report - the label's panel, not all 157 nutrients.

    The nine the 영양성분 표시 mandates (열량, 나트륨, 탄수화물, 당류, 지방,
    트랜스지방, 포화지방, 콜레스테롤, 단백질) and the six a label most often adds.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    food_code: str
    food_name: str | None = None
    nutrient_basis_amount: str | None = None
    energy_kcal: Decimal | None = None
    sodium_mg: Decimal | None = None
    carbohydrate_g: Decimal | None = None
    sugar_g: Decimal | None = None
    fat_g: Decimal | None = None
    trans_fat_g: Decimal | None = None
    saturated_fat_g: Decimal | None = None
    cholesterol_mg: Decimal | None = None
    protein_g: Decimal | None = None
    dietary_fiber_g: Decimal | None = None
    calcium_mg: Decimal | None = None
    iron_mg: Decimal | None = None
    potassium_mg: Decimal | None = None
    vitamin_a_ug_rae: Decimal | None = None
    vitamin_c_mg: Decimal | None = None
    source_name: str | None = None


class FoodItemReportDetailReadResponse(FoodItemReportReadResponse):
    """The report with its edges loaded: its label and its nutrition.

    The type it names is not repeated here: the row already carries
    `product_type_name`, and what the 공전 says about that type - its path
    and its clauses - is the standards route's answer.
    """

    ingredients: list[FoodItemReportIngredientReadResponse]
    nutritions: list[FoodItemReportNutritionReadResponse]
    # How many times the product was declared. A number, not the rows: a
    # product is declared 3.6 times on average and 1,388 times at the widest
    # (2026-09-14), so the rows are their own paged route.
    declaration_count: int
    # How many events an authority published about it - counted at read time,
    # never stored, and here rather than on the list row: 946 events over 1.9M
    # products (2026-09-14), so the number is a section this screen draws only
    # when it is not zero, and the events themselves are their own screen.
    record_count: int
    # Counted over every record of the product, not over a page: the section
    # header states them before a reader opens the rows.
    failed_record_count: int
    last_recorded_on: str | None = None


class FoodSafetyRecordReadResponse(BaseModel):
    """One record about the product - an inspection and its verdict, or an action.

    Read-only, like everything derived. A column of one feed is null on the
    other's rows: a recall has a reason, a method and a grade; an inspection has
    a verdict, and the disposal of one has the item tested, the standard, the
    result and the institution.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    record_key: str
    record_kind: RecordKind
    judgment: str | None = None
    judgment_code: JudgmentCode | None = None
    report_kind: ReportKind | None = None
    item_report_no: str | None = None
    product_name: str | None = None
    business_name: str | None = None
    product_type_name: str | None = None
    recorded_on: str | None = None
    manufactured_text: str | None = None
    # The lot the authority acted on, as a day - on an import, the declaration
    # this event sits on is the one whose 소비기한 starts here.
    lot_date: str | None = None
    reason: str | None = None
    method: str | None = None
    grade: str | None = None
    test_item_name: str | None = None
    standard_text: str | None = None
    test_result_text: str | None = None
    institution_name: str | None = None
    product_name: str | None = None
    business_name: str | None = None
    product_type_name: str | None = None


class FoodItemReportDeclarationReadResponse(BaseModel):
    """One declaration of the product - a 수입신고 or a year's 생산실적.

    Read-only, like everything derived. The product's own columns are not
    repeated here: they are on the report this hangs off. Which half of the
    columns is filled says which kind the row is - an import declaration dates
    itself with 처리일자, a 생산실적 with 보고년도 - and `declaration_kind`
    names it outright.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    declaration_key: str
    declaration_kind: str | None = None
    export_country: str | None = None
    processed_date: str | None = None
    expiry_from: str | None = None
    expiry_to: str | None = None
    report_year: str | None = None
    production_qty_kg: Decimal | None = None
    annual_capacity_kg: Decimal | None = None
    # What an authority published about this lot - counted at read time over
    # `food_safety_record` by `(product, lot_date = expiry_from)`, never stored.
    # 0 on nearly every declaration, which is the truth; the grade is the
    # recall's where one sat on this lot.
    record_count: int = 0
    failed_record_count: int = 0
    recall_grade: str | None = None


class FoodItemReportStandardClauseReadResponse(BaseModel):
    """One clause of a standard - what is measured, against what, judged how.

    `id` is the row's, because nothing else tells two clauses apart: 가공식품
    writes 금속성이물 twice under one heading with the same clause and detail
    (2026-09-09), and a key built from the words rendered a stale row.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    clause_seq: str | None = None
    clause_name: str | None = None
    test_item_code: str
    test_item_name: str | None = None
    detail_item_name: str | None = None
    standard_value: str | None = None
    standard_value_summary: str | None = None
    judgment_format_name: str | None = None
    maximum_value: str | None = None
    minimum_value: str | None = None
    unit_name: str | None = None
    hazard_yn: str | None = None


class FoodItemReportCommonStandardReadResponse(BaseModel):
    """A 제2 clause as it applies to the type: the clause, its node, its 공전 heading path."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    standard: FoodItemReportStandardClauseReadResponse
    inherited_from: FoodItemReportClassificationReadResponse
    heading_path: list[FoodItemReportHeadingReadResponse]


class FoodItemReportHeadingReadResponse(BaseModel):
    """One heading of the 공전's outline."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    common_standard_type_code: str
    standard_name: str | None = None
    level: str | None = None


class FoodItemReportTypeStandardsReadResponse(BaseModel):
    """What the 공전 says about one type the report names."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    node: FoodItemReportClassificationReadResponse
    path: list[FoodItemReportClassificationReadResponse]
    individual_standards: list[FoodItemReportStandardClauseReadResponse]
    common_standards: list[FoodItemReportCommonStandardReadResponse]


class FoodItemReportStandardsReadResponse(BaseModel):
    """`GET /food/item-report/{id}/standards`: one entry per type the report names."""

    model_config = ConfigDict(extra="forbid")

    types: list[FoodItemReportTypeStandardsReadResponse]


class FoodItemReportLabelAllergenReadResponse(BaseModel):
    """One allergen a label declares, as the manufacturer wrote it.

    Kept verbatim (`조개류(굴, 가리비)`): folding the 379 names the two portals use
    onto the 22 법정 알레르겐 would be a claim about safety information this
    harness has no standing to make.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    position: int
    name: str | None = None


class FoodItemReportLabelCautionReadResponse(BaseModel):
    """One 주의사항 문구 a label prints.

    1,198 of the 8,134 rows are the 교차오염 sentence (measured 2026-09-13),
    which is a different fact from the allergens the product contains.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    position: int
    caution_text: str | None = None


class FoodItemReportLabelPackagingReadResponse(BaseModel):
    """One packaging part of a label and what it is made of."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    position: int
    packaging_text: str | None = None


class FoodItemReportLabelBase(BaseModel):
    """The columns of one printed label, whichever portal published it.

    `source` is `food-qr` or `haccp`, and it is half the label's identity: one
    품목보고번호 covers several packages and the two portals hold different ones
    (measured 2026-09-13 on the 56 보고 both carry, 내용량 agrees on 11).

    A column the publishing portal does not answer is null rather than absent -
    HACCP publishes no 유효기간 and none of the 여부 flags.

    `allergen_declaration` is `declared`, `none` or `unknown`, and the last two
    are never the same sentence: 8,479 HACCP rows read 알수없음 (2026-09-13), and
    a screen that renders those as "no allergen" says a package is safe when its
    publisher said it does not know.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int
    source: str
    label_key: str
    allergen_declaration: str
    product_name: str | None = None
    barcode_no: str | None = None
    food_division_name: str | None = None
    food_type_name: str | None = None
    product_type_state: str | None = None
    content_amount_text: str | None = None
    shelf_life_text: str | None = None
    storage_text: str | None = None
    raw_material_text: str | None = None
    intake_method_text: str | None = None
    functional_info_text: str | None = None
    business_name: str | None = None
    maker_name: str | None = None
    seller_name: str | None = None
    representative_name: str | None = None
    site_address: str | None = None
    version_no: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    history_tracked_yn: str | None = None
    irradiated_yn: str | None = None
    gmo_yn: str | None = None
    infant_sale_marked_yn: str | None = None
    high_calorie_low_nutrition_yn: str | None = None
    pasteurized_yn: str | None = None
    sterilized_yn: str | None = None
    refrigerated_yn: str | None = None


class FoodItemReportLabelReadResponse(FoodItemReportLabelBase):
    """One label with what it printed beside it."""

    allergens: list[FoodItemReportLabelAllergenReadResponse]
    cautions: list[FoodItemReportLabelCautionReadResponse]
    packagings: list[FoodItemReportLabelPackagingReadResponse]


class FoodItemReportLabelsReadResponse(BaseModel):
    """`GET /food/item-report/{id}/labels`: one entry per printed label of the report.

    Empty for most reports: the two feeds cover 19,429 labels over 9,750 of the
    1,640,212 reports (2026-09-13).
    """

    model_config = ConfigDict(extra="forbid")

    labels: list[FoodItemReportLabelReadResponse]


class FoodItemReportFilter(BaseModel):
    """What a list may be narrowed by - the query parameters, as one object.

    The fields are the query parameters' names, so the page and its count are
    narrowed by one object and cannot disagree. Two kinds, and the column
    decides: free text (the registry number, the licence, a product or business
    name) matches a fragment; a closed vocabulary matches whole - the kind is
    the pair the schema closes, and the 식품유형 is picked from
    `FoodItemReportFacets`, where `빵` must not stand for `빵류`.
    """

    model_config = ConfigDict(extra="forbid")

    report_kind: ReportKind | None = None
    item_report_no: str | None = None
    license_no: str | None = None
    business_name: str | None = None
    product_name: str | None = None
    product_type_name: str | None = None
    # The one narrowing that is not a column: 161 of 1,072,302 domestic products
    # carry an event (2026-09-14), so a reader looking for one has nothing to
    # type. True keeps the products something was published about; False and
    # None leave the page alone.
    has_events: bool | None = None


class FoodSafetyRecordFilter(BaseModel):
    """What a list of records may be narrowed by - the query parameters, as one object.

    The vocabularies an authority publishes from match whole (what kind of
    record, what it was judged, which registry, which year); the names a reader
    types match a fragment. The date bounds are the publisher's own `YYYYMMDD`
    strings, which compare as text because they are fixed width.
    """

    model_config = ConfigDict(extra="forbid")

    record_kind: RecordKind | None = None
    # Our reading of the portal's verdict, because the portal's own word is
    # Korean data: a screen filters by this and displays `judgment`.
    judgment_code: JudgmentCode | None = None
    # 1,553,789 rows name no product this database holds; a screen about
    # products cannot draw them, so they are out of a page unless asked for.
    mapped: bool = True
    report_kind: ReportKind | None = None
    record_year: str | None = None
    recorded_on_from: str | None = None
    recorded_on_to: str | None = None
    item_report_no: str | None = None
    product_name: str | None = None
    business_name: str | None = None


class FoodSafetyRecordFacets(BaseModel):
    """The closed vocabularies the record selects offer - read off the rows.

    Each feed publishes a small vocabulary and a new value arrives with a
    night's sync, so the options are the table's own distinct values rather
    than a list typed into a screen (the same reason the report facets are).
    """

    model_config = ConfigDict(extra="forbid")

    record_kind: list[RecordKind]
    judgment_code: list[JudgmentCode]
    report_kind: list[ReportKind]
    record_year: list[str]


class FoodItemReportFacets(BaseModel):
    """The closed vocabulary the 식품유형 select offers - the table's own distinct values.

    Read from the rows rather than seeded, for the same reason the raw material
    facets are: the 식품공전 gains a type and the sync brings it the night it
    appears, so a list typed into a screen would offer yesterday's choices.
    Measured 2026-09-10 over 1,640,212 rows: 814 names, 4 rows carrying none.

    Not read off `food_product_classification` (5,944 types): a type no report
    names is an option that can only answer an empty page.
    """

    model_config = ConfigDict(extra="forbid")

    product_type_name: list[str]


# ============================================================
# Functions
# ============================================================


def to_read(item_report: object) -> FoodItemReportReadResponse:
    return FoodItemReportReadResponse.model_validate(item_report)


def to_read_list(item_reports: Sequence[object]) -> list[FoodItemReportReadResponse]:
    return [to_read(item_report) for item_report in item_reports]
