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
