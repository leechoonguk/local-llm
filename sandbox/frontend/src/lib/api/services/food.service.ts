/**
 * Food service — one function per backend endpoint, no more.
 *
 * Three reads and nothing else, because the router has nothing else: the derived
 * table is written by the derive job, not by a request. The list is the page,
 * the detail is one report with its edges, the standards what the Food Code
 * says about the types it names.
 */

import { api } from '@/lib/api/client'
import { FOOD_ENDPOINTS } from '@/lib/api/endpoints'
import type { OffsetLimitParams, Page } from '@/types/api'
import type {
  FoodItemReport,
  FoodItemReportDeclaration,
  FoodItemReportDetail,
  FoodSafetyRecord,
  FoodItemReportFacets,
  FoodItemReportListParams,
  FoodSafetyRecordFacets,
  FoodSafetyRecordListParams,
  FoodItemReportLabels,
  FoodItemReportStandards,
  FoodBusiness,
  FoodBusinessDetail,
  FoodBusinessFacets,
  FoodBusinessListParams,
  FoodRawMaterial,
  FoodRawMaterialDetail,
  FoodRawMaterialFacets,
  FoodRawMaterialListParams,
} from '@/types/food'

export const foodService = {
  listItemReports: (params: FoodItemReportListParams) =>
    api.get<Page<FoodItemReport>>(FOOD_ENDPOINTS.ITEM_REPORT_LIST, { params }),

  listSafetyRecords: (params: FoodSafetyRecordListParams) =>
    api.get<Page<FoodSafetyRecord>>(FOOD_ENDPOINTS.SAFETY_RECORD_LIST, { params }),

  safetyRecordFacets: () =>
    api.get<FoodSafetyRecordFacets>(FOOD_ENDPOINTS.SAFETY_RECORD_FACETS),

  itemReportFacets: () => api.get<FoodItemReportFacets>(FOOD_ENDPOINTS.ITEM_REPORT_FACETS),

  getItemReport: (id: string) => api.get<FoodItemReportDetail>(FOOD_ENDPOINTS.ITEM_REPORT_DETAIL(id)),

  itemReportDeclarations: (id: string, params: OffsetLimitParams) =>
    api.get<Page<FoodItemReportDeclaration>>(FOOD_ENDPOINTS.ITEM_REPORT_DECLARATIONS(id), {
      params,
    }),

  itemReportSafetyRecords: (id: string, params: OffsetLimitParams) =>
    api.get<Page<FoodSafetyRecord>>(FOOD_ENDPOINTS.ITEM_REPORT_SAFETY_RECORDS(id), { params }),

  getItemReportStandards: (id: string) =>
    api.get<FoodItemReportStandards>(FOOD_ENDPOINTS.ITEM_REPORT_STANDARDS(id)),

  getItemReportLabels: (id: string) =>
    api.get<FoodItemReportLabels>(FOOD_ENDPOINTS.ITEM_REPORT_LABELS(id)),

  listRawMaterials: (params: FoodRawMaterialListParams) =>
    api.get<Page<FoodRawMaterial>>(FOOD_ENDPOINTS.RAW_MATERIAL_LIST, { params }),

  rawMaterialFacets: () => api.get<FoodRawMaterialFacets>(FOOD_ENDPOINTS.RAW_MATERIAL_FACETS),

  getRawMaterial: (id: string) =>
    api.get<FoodRawMaterialDetail>(FOOD_ENDPOINTS.RAW_MATERIAL_DETAIL(id)),

  rawMaterialItemReports: (id: string, params: OffsetLimitParams) =>
    api.get<Page<FoodItemReport>>(FOOD_ENDPOINTS.RAW_MATERIAL_ITEM_REPORTS(id), { params }),

  listBusinesses: (params: FoodBusinessListParams) =>
    api.get<Page<FoodBusiness>>(FOOD_ENDPOINTS.BUSINESS_LIST, { params }),

  businessFacets: () => api.get<FoodBusinessFacets>(FOOD_ENDPOINTS.BUSINESS_FACETS),

  getBusiness: (id: string) => api.get<FoodBusinessDetail>(FOOD_ENDPOINTS.BUSINESS_DETAIL(id)),

  /** One turn of chat, as the events arrive; the signal is what stops it early. */
  chat: (message: string, signal?: AbortSignal) =>
    api.stream(FOOD_ENDPOINTS.CHAT, { message }, signal),
}
