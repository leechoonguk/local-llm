/**
 * Batch query/mutation hooks — same shape as the user domain.
 *
 * The list is cached for `STANDARD` rather than refetched every mount: batches
 * are read far more often than they change, and the backend already serves this
 * collection from Redis with a 60s TTL.
 */

import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { QUERY_STALE_TIME } from '@/lib/api/queryDefaults'
import { batchKeys, batchRunKeys, batchStepKeys } from '@/lib/api/queryKeys'
import { batchService } from '@/lib/api/services/batch.service'
import type { OffsetLimitParams } from '@/types/api'
import type {
  Batch,
  BatchCreateRequest,
  BatchListParams,
  BatchRun,
  BatchRunRequest,
  BatchRunStatus,
  BatchUpdateRequest,
} from '@/types/batch'

/**
 * How many schedules the header's failure feed watches, and how far back into
 * each one's log it reads.
 *
 * The backend has no cross-schedule run endpoint — runs are read per schedule
 * (`BATCH_ENDPOINTS.RUNS`) — so the feed is one request per schedule, bounded
 * here rather than left to the size of the table. Five rows covers a nightly
 * job's last five nights; a failure older than the window below is not news.
 */
const WATCHED_SCHEDULES = 50

const RECENT_RUNS_PER_SCHEDULE = 5

/** A failure the reader has not had a working day to see yet. */
const FAILURE_WINDOW_MS = 24 * 60 * 60 * 1000

/**
 * The two endings that are failures. `STOPPED` is a person's decision and
 * `SKIPPED` is a job standing down on purpose — neither is news.
 */
const FAILURE_STATUSES: readonly BatchRunStatus[] = ['FAILED', 'INTERRUPTED']

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

/** One failed execution, carrying the schedule it belongs to. */
export interface BatchFailure {
  run: BatchRun
  batch: Batch
}

/**
 * Every schedule's recent failures, newest first — what the header's bell counts.
 *
 * One request per schedule, because that is the only shape the API has: runs are
 * read per schedule (`GET /batch/{id}/runs`) and there is no endpoint that
 * crosses them. The fan-out is bounded by `WATCHED_SCHEDULES` and each query
 * uses `batchRunKeys` — the *same* key the runs dialog uses — so opening a
 * schedule's log after reading its failure here costs no second request.
 *
 * It collapses to one query the day the backend grows a cross-schedule endpoint;
 * until then the alternative is a bell that knows nothing until someone opens a
 * dialog per schedule.
 *
 * `REALTIME`, for the run log's own reason: the scheduler writes these rows
 * outside HTTP, so nothing this client does can invalidate them and a cached
 * answer would report last night's failure as still unseen after a refresh.
 */
export function useBatchFailureFeed(): { failures: BatchFailure[]; isLoading: boolean } {
  const schedules = useBatchList({ offset: 0, limit: WATCHED_SCHEDULES })
  const batches = schedules.data?.items ?? []

  const logs = useQueries({
    queries: batches.map((batch) => ({
      queryKey: batchRunKeys.list({
        batchId: batch.id,
        offset: 0,
        limit: RECENT_RUNS_PER_SCHEDULE,
      }),
      queryFn: () =>
        batchService.runs(batch.id, { offset: 0, limit: RECENT_RUNS_PER_SCHEDULE }),
      staleTime: QUERY_STALE_TIME.REALTIME,
    })),
  })

  // Recomputed per render rather than memoised: `useQueries` hands back a new
  // array every time, so a memo keyed on it would recompute anyway while
  // claiming not to. The work is bounded by the two constants above.
  //
  // The window is measured from **when the log was fetched**, not from the clock:
  // reading `Date.now()` while rendering makes the same state produce different
  // output on a re-render React is free to perform (and `react-hooks/purity`
  // refuses it). `dataUpdatedAt` moves when the data does, which is also the only
  // moment the answer can change.
  const failures = logs.flatMap((log, index) => {
    const batch = batches[index]
    if (batch === undefined) return []
    const since = log.dataUpdatedAt - FAILURE_WINDOW_MS
    return (log.data?.items ?? [])
      .filter((run) => FAILURE_STATUSES.includes(run.status))
      .filter((run) => Date.parse(run.started_at) >= since)
      .map((run) => ({ run, batch }))
  })
  failures.sort((left, right) => Date.parse(right.run.started_at) - Date.parse(left.run.started_at))

  return { failures, isLoading: schedules.isLoading || logs.some((log) => log.isLoading) }
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
