/**
 * Batch domain types — mirror of `backend/app/schemas/batch.py`.
 *
 * A batch row is a schedule: `code` names the job the server can run, `cron`
 * says when, and `enabled` is the stop switch. `code` is absent from the update
 * request on purpose — the server refuses to repoint a schedule at another job.
 */

import type { AuditedResource } from '@/types/api'

export interface Batch extends AuditedResource {
  code: string
  name: string
  description: string | null
  cron: string
  enabled: boolean
}

export interface BatchCreateRequest {
  code: string
  name: string
  description?: string | null
  cron: string
  enabled?: boolean
}

export interface BatchUpdateRequest {
  name?: string | null
  description?: string | null
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
  status: string
  trigger: string
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
  status: string
  range_start: number | null
  range_end: number | null
  received: number | null
  written: number | null
  duration_ms: number
  integration_call_id: string | null
  error_code: string | null
  error_detail: string | null
}
