/**
 * Batch domain types — mirror of `backend/app/schemas/batch.py`.
 *
 * A batch row is a schedule: `code` names the job the server can run, `cron`
 * says when, and `enabled` is the stop switch. `code` is absent from the update
 * request on purpose — the server refuses to repoint a schedule at another job.
 */

import type { AuditedResource, BatchFilterParams, PageParams } from '@/types/api'

/**
 * A run's five endings — `ck_batch_run_status`, verbatim.
 *
 * Narrowed rather than `string` because the vocabulary is closed by a CHECK
 * constraint: widening it here is what forced the status→colour map to be
 * keyed by `string` and to carry an unreachable `?? 'default'`. As a union the
 * compiler owns exhaustiveness, so a sixth ending added to the constraint
 * fails the build instead of rendering as a grey badge nobody notices.
 */
export type BatchRunStatus =
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'STOPPED'
  | 'INTERRUPTED'
  | 'SKIPPED'

/** What started a run — `ck_batch_run_trigger`, verbatim. */
export type BatchTrigger = 'CRON' | 'MANUAL'

/**
 * A step's two endings — `ck_batch_step_status`, verbatim.
 *
 * A narrower set than a run's, and deliberately its own type: rows are written
 * **after** the unit ends, so a step is never `RUNNING`.
 */
export type BatchStepStatus = 'SUCCEEDED' | 'FAILED'

export interface Batch extends AuditedResource {
  /**
   * Whether an execution is in flight right now, as the scheduler answers at
   * read time. Not a stored column: the list is cached and a run lasts seconds.
   */
  running: boolean
  code: string
  cron: string
  enabled: boolean
}

export interface BatchCreateRequest {
  code: string
  cron: string
  enabled?: boolean
}

export interface BatchUpdateRequest {
  cron?: string | null
  enabled?: boolean | null
}

export interface BatchRunRequest {
  running: boolean
}

export interface BatchRunResponse {
  id: string
  code: string
  running: boolean
}

/** One execution of a schedule — mirror of `BatchRunReadResponse`. */
export interface BatchRun extends AuditedResource {
  batch_id: string | null
  code: string
  status: BatchRunStatus
  trigger: BatchTrigger
  triggered_by: string
  stopped_by: string | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  result: number | null
  error_code: string | null
  error_detail: string | null
}

/** One unit inside a run — mirror of `BatchStepReadResponse`. */
export interface BatchStep extends AuditedResource {
  run_id: string
  sequence: number
  status: BatchStepStatus
  range_start: number | null
  range_end: number | null
  received: number | null
  written: number | null
  duration_ms: number
  integration_call_id: string | null
  error_code: string | null
  error_detail: string | null
}

/**
 * What `GET /batch/` accepts: the page plus one filter per filterable column.
 *
 * The intersection lives with the domain rather than in the shared params type,
 * so an endpoint that takes no filter keeps a params type that matches it.
 */
export type BatchListParams = PageParams & BatchFilterParams
