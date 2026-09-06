/**
 * Food query hooks — the caching half of the food domain.
 *
 * Queries only: no mutation exists here, because the rows change when the
 * nightly sync runs, not when a user clicks. That is also why the staleness is
 * `REALTIME`: a cache window is only safe when a write on this side can cut it
 * short by invalidating the key, and no write here can - so the query refetches
 * on mount and focus, and the toolbar's refresh covers the reader who knows a
 * sync just ran (`check-frontend-api-layer`).
 */

import { useQuery } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { foodRawMaterialKeys } from '@/lib/api/queryKeys'
import { foodService } from '@/lib/api/services/food.service'
import type { FoodRawMaterialListParams } from '@/types/food'

export function useFoodRawMaterialList(params: FoodRawMaterialListParams) {
  return useQuery({
    queryKey: foodRawMaterialKeys.list(params),
    queryFn: () => foodService.listRawMaterials(params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
  })
}

/** The select filters' options. Same staleness as the list, for the same reason. */
export function useFoodRawMaterialFacets() {
  return useQuery({
    queryKey: foodRawMaterialKeys.list({ facets: true }),
    queryFn: () => foodService.rawMaterialFacets(),
    staleTime: QUERY_STALE_TIME.REALTIME,
  })
}
