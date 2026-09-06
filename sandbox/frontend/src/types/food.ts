/**
 * Food domain types — mirror of `backend/app/schemas/food/raw_material.py`.
 *
 * Read side only. The `food_*` tables are ledgers a nightly batch fills from the
 * provider, so there is no create or update request type here: a row typed on
 * this side would be overwritten by the next sync, and the router has no verb to
 * accept it (rule://backend-domain, "Ledger Domains Are Read-Only Over HTTP").
 */

import type { AuditedResource, FoodRawMaterialFilterParams, OffsetLimitParams } from '@/types/api'

export interface FoodRawMaterial extends AuditedResource {
  raw_material_code: string
  representative_raw_material_name: string | null
  raw_material_alias: string | null
  english_name: string | null
  scientific_name: string | null
  raw_material_large_class: string | null
  raw_material_medium_class: string | null
  region_code: string | null
  region_code_name: string | null
  process_code: string | null
  process_code_name: string | null
  raw_material_status_code: string | null
  raw_material_status_code_name: string | null
  valid_start_date: string | null
  valid_end_date: string | null
  use_yn: string | null
  source_updated_at: string | null
}

/** What `GET /food/raw-material/` accepts: the page plus one filter per filterable column. */
export type FoodRawMaterialListParams = OffsetLimitParams & FoodRawMaterialFilterParams

/**
 * Mirror of `FoodRawMaterialFacets`: the values the three select filters offer,
 * read from the ledger's own rows so a vocabulary the sync brought tonight is a
 * choice tomorrow morning.
 */
export interface FoodRawMaterialFacets {
  raw_material_large_class: string[]
  raw_material_medium_class: string[]
  /** The medium classes under each large class - the child select's options once a parent is chosen. */
  raw_material_medium_class_by_large: Record<string, string[]>
  raw_material_status_code_name: string[]
}
