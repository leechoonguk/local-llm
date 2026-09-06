/**
 * Batch query/mutation hooks — same shape as the user domain.
 *
 * The list is cached for `STANDARD` rather than refetched every mount: batches
 * are read far more often than they change, and the backend already serves this
 * collection from Redis with a 60s TTL.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { batchKeys, batchRunKeys, batchStepKeys } from '@/lib/api/queryKeys'
import { batchService } from '@/lib/api/services/batch.service'
import type { OffsetLimitParams } from '@/types/api'
import type {
  BatchCreateRequest,
  BatchListParams,
  BatchRunRequest,
  BatchUpdateRequest,
} from '@/types/batch'

export function useBatchList(params: BatchListParams) {
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

/**
 * One schedule's executions, newest first.
 *
 * REALTIME rather than STANDARD: the rows are written by the scheduler outside
 * HTTP, so nothing this client does can produce one — a stale answer would show
 * last night's failure as still running with no way to refresh it. The key is
 * `batchRunKeys`, a scope of its own, because `batchKeys.list({scope:'runs'})`
 * sat under the prefix a schedule's mutations invalidate (see `queryKeys.ts`).
 */
export function useBatchRunList(batchId: string | null, params: OffsetLimitParams) {
  return useQuery({
    queryKey: batchRunKeys.list({ batchId, ...params }),
    queryFn: () => batchService.runs(batchId ?? '', params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
    enabled: batchId !== null,
  })
}

/** One run's units, in the order they happened — same freshness reasoning. */
export function useBatchRunStepList(
  batchId: string | null,
  runId: string | null,
  params: OffsetLimitParams,
) {
  return useQuery({
    queryKey: batchStepKeys.list({ batchId, runId, ...params }),
    queryFn: () => batchService.runSteps(batchId ?? '', runId ?? '', params),
    staleTime: QUERY_STALE_TIME.REALTIME,
    placeholderData: (previous) => previous,
    enabled: batchId !== null && runId !== null,
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
