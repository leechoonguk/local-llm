/**
 * Food domain types — mirror of `backend/app/schemas/food/item_report.py`.
 *
 * Read side only. The `food_*` tables the API serves are derived: the derive job
 * rebuilds them whole off the ledgers every night, so there is no create or
 * update request type here - a row typed on this side would be gone by morning,
 * and the router has no verb to accept it (rule://backend-domain, "Ledgers Have
 * No Route; Derived Tables Are Read-Only Over HTTP").
 */

import type {
  AuditedResource,
  FoodBusinessFilterParams,
  FoodItemReportFilterParams,
  FoodRawMaterialFilterParams,
  PageParams,
} from '@/types/api'

/** Which registry reported the product - `ReportKind` on the server. */
export type ReportKind = 'domestic' | 'livestock' | 'import' | 'health_functional'

/**
 * The kind's whole vocabulary - the schema's Literal, not a table's values, so
 * it is fixed here. Ordered the way a reader meets them: the three registries
 * that file a 품목제조보고/신고 first, then the one that files a 수입신고, so
 * 수입식품 does not sit between two domestic registries in a filter list.
 */
export const REPORT_KINDS: readonly ReportKind[] = [
  'domestic',
  'livestock',
  'health_functional',
  'import',
]

export interface FoodItemReport extends AuditedResource {
  report_kind: ReportKind
  item_report_no: string
  license_no: string | null
  business_name: string | null
  maker_name: string | null
  origin_country: string | null
  report_date: string | null
  product_name: string | null
  product_name_en: string | null
  primary_functionality: string | null
  intake_caution: string | null
  storage_method: string | null
  standard_spec: string | null
  functional_indicator: string | null
  product_type_name: string | null
  production_ended: string | null
  high_calorie_low_nutrition: string | null
  child_favorite_certified_yn: string | null
  shelf_life: string | null
  industry_name: string | null
  quality_maintenance_days: string | null
  usage_method: string | null
  purpose: string | null
  product_form: string | null
  packaging_material: string | null
  domestic_export_type: string | null
  source_updated_at: string | null
  /** How many events the product carries - counted for the page, 0 where none. */
}

/** The Food Code type a report names - `FoodItemReportClassificationReadResponse`. */
export interface FoodItemReportClassification {
  id: string
  version: number
  product_code: string
  korean_name: string | null
  level: string | null
  root_product_code: string | null
}

/** One ingredient of the report, in label order - `FoodItemReportIngredientReadResponse`. */
export interface FoodItemReportIngredient {
  id: string
  version: number
  position: number
  ordinal: number | null
  name: string
  /** Which of a registry's lists the name came from; null where it publishes one. */
  ingredient_role: string | null
}

/** The nutrition record naming this report - `FoodItemReportNutritionReadResponse`; amounts arrive as decimal strings. */
export const LABEL_NUTRIENTS = [
  'energy_kcal',
  'sodium_mg',
  'carbohydrate_g',
  'sugar_g',
  'fat_g',
  'trans_fat_g',
  'saturated_fat_g',
  'cholesterol_mg',
  'protein_g',
  'dietary_fiber_g',
  'calcium_mg',
  'iron_mg',
  'potassium_mg',
  'vitamin_a_ug_rae',
  'vitamin_c_mg',
] as const

export interface FoodItemReportNutrition {
  id: string
  version: number
  food_code: string
  food_name: string | null
  nutrient_basis_amount: string | null
  energy_kcal: string | null
  sodium_mg: string | null
  carbohydrate_g: string | null
  sugar_g: string | null
  fat_g: string | null
  trans_fat_g: string | null
  saturated_fat_g: string | null
  cholesterol_mg: string | null
  protein_g: string | null
  dietary_fiber_g: string | null
  calcium_mg: string | null
  iron_mg: string | null
  potassium_mg: string | null
  vitamin_a_ug_rae: string | null
  vitamin_c_mg: string | null
  source_name: string | null
}

/** `GET /food/item-report/{id}`: the report with its three edges loaded. */
export interface FoodItemReportDetail extends FoodItemReport {
  record_count: number
  /** Counted over every record of the product, not over one page. */
  failed_record_count: number
  last_recorded_on: string | null
  ingredients: FoodItemReportIngredient[]
  nutritions: FoodItemReportNutrition[]
  declaration_count: number
}

/**
 * Our reading of the portal's verdict - the schema's own Literal.
 *
 * This is the word the screen prints, filters, counts and colours by. The
 * portal's own text travels beside it as `judgment` and is four spellings of
 * these three (검토중 is pending; 상기와같음 is passed, on 111,522 rows, and
 * says nothing to a reader): a badge spelled one way beside a filter spelled
 * the other reads like the filter missed.
 */
export type JudgmentCode = 'failed' | 'passed' | 'pending'

export const JUDGMENT_CODES: readonly JudgmentCode[] = ['failed', 'passed', 'pending']

/** What kind of record it is - a finding or an action; the schema's own Literal. */
export type RecordKind = 'recall' | 'inspection_failure' | 'collection_inspection'

export const RECORD_KINDS: readonly RecordKind[] = [
  'recall',
  'inspection_failure',
  'collection_inspection',
]

/** One event published about the product - `FoodSafetyRecordReadResponse`. */
export interface FoodSafetyRecord {
  id: string
  version: number
  record_key: string
  record_kind: RecordKind
  /** What the inspection found, as published - null on a recall, which is an action. */
  judgment: string | null
  judgment_code: JudgmentCode | null
  report_kind: ReportKind | null
  item_report_no: string | null
  recorded_on: string | null
  manufactured_text: string | null
  lot_date: string | null
  reason: string | null
  method: string | null
  grade: string | null
  test_item_name: string | null
  standard_text: string | null
  test_result_text: string | null
  institution_name: string | null
  product_name: string | null
  business_name: string | null
  product_type_name: string | null
}

/** One declaration of the product - `FoodItemReportDeclarationReadResponse`. */
export interface FoodItemReportDeclaration {
  id: string
  version: number
  declaration_key: string
  declaration_kind: string | null
  export_country: string | null
  processed_date: string | null
  expiry_from: string | null
  expiry_to: string | null
  report_year: string | null
  production_qty_kg: string | null
  annual_capacity_kg: string | null
  record_count: number
  failed_record_count: number
  recall_grade: string | null
}

/** What `GET /food/item-report/` accepts: the page plus one filter per filterable column. */
export type FoodItemReportListParams = PageParams & FoodItemReportFilterParams

/**
 * The 식품유형 select's options: the table's own distinct type names, read from
 * the rows. Measured 2026-09-10: 814 over 1,640,212 reports. Not the 공전's
 * 5,944 types - a type no report names is an option that answers an empty page.
 */
export interface FoodItemReportFacets {
  product_type_name: string[]
}

/** One clause of a standard - `FoodItemReportStandardClauseReadResponse`. */
export interface FoodItemReportStandardClause {
  id: string
  version: number
  clause_seq: string | null
  clause_name: string | null
  test_item_code: string
  test_item_name: string | null
  detail_item_name: string | null
  standard_value: string | null
  standard_value_summary: string | null
  judgment_format_name: string | null
  maximum_value: string | null
  minimum_value: string | null
  unit_name: string | null
  hazard_yn: string | null
}

/** One heading of the Food Code's outline - `FoodItemReportHeadingReadResponse`. */
export interface FoodItemReportHeading {
  id: string
  version: number
  common_standard_type_code: string
  standard_name: string | null
  level: string | null
}

/** A common clause as it applies to a type - `FoodItemReportCommonStandardReadResponse`. */
export interface FoodItemReportCommonStandard {
  standard: FoodItemReportStandardClause
  inherited_from: FoodItemReportClassification
  heading_path: FoodItemReportHeading[]
}

/** What the Food Code says about one type the report names - `FoodItemReportTypeStandardsReadResponse`. */
export interface FoodItemReportTypeStandards {
  node: FoodItemReportClassification
  path: FoodItemReportClassification[]
  individual_standards: FoodItemReportStandardClause[]
  common_standards: FoodItemReportCommonStandard[]
}

/** `GET /food/item-report/{id}/standards` - `FoodItemReportStandardsReadResponse`. */
export interface FoodItemReportStandards {
  types: FoodItemReportTypeStandards[]
}

/** One allergen a label declares, verbatim - `FoodItemReportLabelAllergenReadResponse`. */
export interface FoodItemReportLabelAllergen {
  id: string
  version: number
  position: number
  name: string | null
}

/** One caution sentence a label prints - `FoodItemReportLabelCautionReadResponse`. */
export interface FoodItemReportLabelCaution {
  id: string
  version: number
  position: number
  caution_text: string | null
}

/** One packaging part of a label - `FoodItemReportLabelPackagingReadResponse`. */
export interface FoodItemReportLabelPackaging {
  id: string
  version: number
  position: number
  packaging_text: string | null
}

/** One printed label of a report, from either portal - `FoodItemReportLabelReadResponse`. */
export interface FoodItemReportLabel {
  id: string
  version: number
  source: string
  label_key: string
  allergen_declaration: string
  product_name: string | null
  barcode_no: string | null
  food_division_name: string | null
  food_type_name: string | null
  product_type_state: string | null
  content_amount_text: string | null
  shelf_life_text: string | null
  storage_text: string | null
  raw_material_text: string | null
  intake_method_text: string | null
  functional_info_text: string | null
  business_name: string | null
  maker_name: string | null
  seller_name: string | null
  representative_name: string | null
  site_address: string | null
  version_no: string | null
  valid_from: string | null
  valid_to: string | null
  history_tracked_yn: string | null
  irradiated_yn: string | null
  gmo_yn: string | null
  infant_sale_marked_yn: string | null
  high_calorie_low_nutrition_yn: string | null
  pasteurized_yn: string | null
  sterilized_yn: string | null
  refrigerated_yn: string | null
  allergens: FoodItemReportLabelAllergen[]
  cautions: FoodItemReportLabelCaution[]
  packagings: FoodItemReportLabelPackaging[]
}

/** `GET /food/item-report/{id}/labels` - `FoodItemReportLabelsReadResponse`. */
export interface FoodItemReportLabels {
  labels: FoodItemReportLabel[]
}

/**
 * Which registry printed a label. The three are never merged: one 품목보고번호
 * covers several packages and the registries hold different ones, so a screen
 * shows every label it has.
 */
export const FOOD_QR_LABEL_SOURCE = 'food-qr'
export const HACCP_LABEL_SOURCE = 'haccp'
export const IMPORT_LABEL_SOURCE = 'import'
export const LABEL_SOURCES = [
  FOOD_QR_LABEL_SOURCE,
  HACCP_LABEL_SOURCE,
  IMPORT_LABEL_SOURCE,
] as const
export type LabelSource = (typeof LABEL_SOURCES)[number]

/**
 * What a label says about allergens, which is three states and not two. A
 * publisher that wrote 알수없음 (8,479 of the HACCP feed's 14,664 rows, measured
 * 2026-09-13) has not said the package is free of them.
 */
export const ALLERGEN_DECLARED = 'declared'
export const ALLERGEN_NONE = 'none'

/**
 * The declaration columns a label prints as a Y/N flag, in the order the tab
 * shows them. Only the Food QR portal publishes them; a HACCP label reads null
 * for every one.
 */
export const LABEL_FLAGS = [
  'history_tracked_yn',
  'irradiated_yn',
  'gmo_yn',
  'infant_sale_marked_yn',
  'high_calorie_low_nutrition_yn',
  'pasteurized_yn',
  'sterilized_yn',
  'refrigerated_yn',
] as const satisfies readonly (keyof FoodItemReportLabel)[]

/**
 * The label fields the tab lists as plain text, in printed order. A null is what
 * the publishing portal does not answer, and the field shows a dash for it.
 */
export const LABEL_FIELDS = [
  'barcode_no',
  'food_type_name',
  'content_amount_text',
  'shelf_life_text',
  'storage_text',
  'food_division_name',
  'maker_name',
  'seller_name',
  'business_name',
  'site_address',
] as const satisfies readonly (keyof FoodItemReportLabel)[]
/** Whether the portal still lists a code - `UseFlag` on the server. */
export type UseFlag = 'Y' | 'N'

/** The pair as the filter select offers it; the labels read through the locale. */
export const USE_FLAGS: readonly UseFlag[] = ['Y', 'N']

/** Mirror of `backend/app/schemas/food/raw_material.py` - a derived table, read only. */
export interface FoodRawMaterial extends AuditedResource {
  raw_material_code: string
  base_code: string
  representative_raw_material_name: string | null
  raw_material_alias: string | null
  english_name: string | null
  scientific_name: string | null
  raw_material_large_class: string | null
  raw_material_medium_class: string | null
  region_code_name: string | null
  process_code_name: string | null
  raw_material_status_code_name: string | null
  use_yn: string | null
  source_updated_at: string | null
}

/** The material with its composition's siblings - every code of the same base, itself included. */
export interface FoodRawMaterialDetail extends FoodRawMaterial {
  variants: FoodRawMaterial[]
}

export type FoodRawMaterialListParams = PageParams & FoodRawMaterialFilterParams

/**
 * The select filters' options: the table's own distinct values, read from the
 * rows. The medium class comes twice - flat, and grouped under each large class
 * it appears in - so the child select narrows once a parent is chosen.
 */
export interface FoodRawMaterialFacets {
  raw_material_large_class: string[]
  raw_material_medium_class: string[]
  raw_material_medium_class_by_large: Record<string, string[]>
  raw_material_status_code_name: string[]
}

/** Which ledger a business row came from - `BusinessStatus` on the server. */
export type BusinessStatus = 'ACTIVE' | 'CLOSED'

/** The pair as the filter select offers it; the labels read through the locale. */
export const BUSINESS_STATUSES: readonly BusinessStatus[] = ['ACTIVE', 'CLOSED']

/** Mirror of `backend/app/schemas/food/business.py` - a derived table, read only. */
export interface FoodBusiness extends AuditedResource {
  license_no: string
  industry_name: string | null
  business_name: string | null
  permit_date: string | null
  district: string | null
  status: BusinessStatus
  closed_date: string | null
  closure_kind: string | null
  institution_name: string | null
  site_key: string | null
  name_key: string | null
}

/**
 * The business with the rows it shares a name or a site with. Neither list is a
 * claim of one owner: nothing public keys a licence to a 법인등록번호.
 */
export interface FoodBusinessDetail extends FoodBusiness {
  same_name: FoodBusiness[]
  same_site: FoodBusiness[]
}

export type FoodBusinessListParams = PageParams & FoodBusinessFilterParams

/** The industry select's options: the table's own distinct values. */
export interface FoodBusinessFacets {
  industry_name: string[]
}

/** Mirror of `backend/app/schemas/food/chat.py` - a stream's events, not rows. */
export interface FoodChatTokenEvent {
  text: string
}

export interface FoodChatEndEvent {
  text: string
  tokens: number
}

export interface FoodChatErrorEvent {
  code: string
}

/** One conversation: its turns, in the order they were said. */
export interface FoodChatConversation {
  id: string
  turns: FoodChatTurn[]
}

/** One turn on screen: who said it, and what has arrived of it so far. */
export interface FoodChatTurn {
  id: string
  author: 'user' | 'assistant'
  text: string
  /** True while tokens are still landing on this turn. */
  streaming: boolean
}

/** The vocabularies the event screen's selects offer, read off the table. */
export interface FoodSafetyRecordFacets {
  record_kind: string[]
  judgment_code: string[]
  report_kind: string[]
  record_year: string[]
}

/** What the event list may be narrowed by - the query the screen sends. */
export interface FoodSafetyRecordFilterParams {
  record_kind?: string
  judgment_code?: string
  /** Records naming no product this database holds are out of the page unless false. */
  mapped?: boolean
  report_kind?: string
  record_year?: string
  recorded_on_from?: string
  recorded_on_to?: string
  item_report_no?: string
  product_name?: string
  business_name?: string
}

/** The event list's query: the page plus whatever the boxes hold. */
export type FoodSafetyRecordListParams = PageParams & FoodSafetyRecordFilterParams
