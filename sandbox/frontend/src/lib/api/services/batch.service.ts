/**
 * Batch service — one function per backend endpoint, no more.
 */

import { api } from '@/lib/api/client'
import { BATCH_ENDPOINTS } from '@/lib/api/endpoints'
import type { OffsetLimitParams, OkResponse, Page } from '@/types/api'
import type {
  Batch,
  BatchCreateRequest,
  BatchListParams,
  BatchRun,
  BatchRunRequest,
  BatchRunResponse,
  BatchStep,
  BatchUpdateRequest,
} from '@/types/batch'

export const batchService = {
  list: (params: BatchListParams) => api.get<Page<Batch>>(BATCH_ENDPOINTS.LIST, { params }),

  detail: (id: string) => api.get<Batch>(BATCH_ENDPOINTS.DETAIL(id)),

  create: (data: BatchCreateRequest) => api.post<Batch>(BATCH_ENDPOINTS.CREATE, data),

  update: (id: string, data: BatchUpdateRequest) =>
    api.patch<Batch>(BATCH_ENDPOINTS.UPDATE(id), data),

  remove: (id: string) => api.delete<OkResponse>(BATCH_ENDPOINTS.DELETE(id)),

  run: (id: string, data: BatchRunRequest) =>
    api.post<BatchRunResponse>(BATCH_ENDPOINTS.RUN(id), data),

  runs: (id: string, params: OffsetLimitParams) =>
    api.get<Page<BatchRun>>(BATCH_ENDPOINTS.RUNS(id), { params }),

  runSteps: (batchId: string, runId: string, params: OffsetLimitParams) =>
    api.get<Page<BatchStep>>(BATCH_ENDPOINTS.RUN_STEPS(batchId, runId), { params }),
}
