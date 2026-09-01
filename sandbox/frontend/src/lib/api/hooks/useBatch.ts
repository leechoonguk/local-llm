/**
 * Batch query/mutation hooks — same shape as the user domain.
 *
 * The list is cached for `STANDARD` rather than refetched every mount: batches
 * are read far more often than they change, and the backend already serves this
 * collection from Redis with a 60s TTL.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { batchKeys } from '@/lib/api/queryKeys'
import { batchService } from '@/lib/api/services/batch.service'
import type { OffsetLimitParams } from '@/types/api'
import type { BatchCreateRequest, BatchRunRequest, BatchUpdateRequest } from '@/types/batch'

export function useBatchList(params: OffsetLimitParams) {
  return useQuery({
    queryKey: batchKeys.list(params),
    queryFn: () => batchService.list(params),
    staleTime: QUERY_STALE_TIME.STANDARD,
    placeholderData: (previous) => previous,
  })
}

export function useBatch(id: string | null) {
  return useQuery({
    queryKey: batchKeys.detail(id ?? ''),
    queryFn: () => batchService.detail(id ?? ''),
    staleTime: QUERY_STALE_TIME.STANDARD,
    enabled: id !== null,
  })
}

export function useCreateBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: BatchCreateRequest) => batchService.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: batchKeys.lists() }),
  })
}

export function useUpdateBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: BatchUpdateRequest }) =>
      batchService.update(id, data),
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: batchKeys.lists() })
      queryClient.invalidateQueries({ queryKey: batchKeys.detail(batch.id) })
    },
  })
}

export function useDeleteBatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => batchService.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: batchKeys.lists() }),
  })
}

/**
 * Run or stop one execution.
 *
 * No cache invalidation: an execution changes no row, so refetching the list
 * would only make the grid flicker for a state it does not display.
 */
export function useRunBatch() {
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: BatchRunRequest }) =>
      batchService.run(id, data),
  })
}
