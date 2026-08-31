/**
 * Batch domain types — mirror of `backend/app/schemas/batch.py`.
 */

import type { AuditedResource } from '@/types/api'

export interface Batch extends AuditedResource {
  name: string
  description: string | null
}

export interface BatchCreateRequest {
  name: string
  description?: string | null
}

export interface BatchUpdateRequest {
  name?: string | null
  description?: string | null
}
