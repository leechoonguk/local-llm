/**
 * Food service — one function per backend endpoint, no more.
 *
 * Two reads and nothing else, because the router has nothing else: the ledger
 * is written by the sync, not by a request, and the grid is the whole screen.
 * `facets` is what the select filters offer - the ledger's distinct values.
 */

import { api } from '@/lib/api/client'
import { FOOD_ENDPOINTS } from '@/lib/api/endpoints'
import type { Page } from '@/types/api'
import type { FoodRawMaterial, FoodRawMaterialFacets, FoodRawMaterialListParams } from '@/types/food'

export const foodService = {
  listRawMaterials: (params: FoodRawMaterialListParams) =>
    api.get<Page<FoodRawMaterial>>(FOOD_ENDPOINTS.RAW_MATERIAL_LIST, { params }),

  rawMaterialFacets: () => api.get<FoodRawMaterialFacets>(FOOD_ENDPOINTS.RAW_MATERIAL_FACETS),
}
