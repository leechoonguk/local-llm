/**
 * Batch service — one function per backend endpoint, no more.
 */

import { api } from '@/lib/api/client'
import { BATCH_ENDPOINTS } from '@/lib/api/endpoints'
import type { OffsetLimitParams, OkResponse } from '@/types/api'
import type { Batch, BatchCreateRequest, BatchUpdateRequest } from '@/types/batch'

export const batchService = {
  list: (params: OffsetLimitParams) => api.get<Batch[]>(BATCH_ENDPOINTS.LIST, { params }),

  detail: (id: string) => api.get<Batch>(BATCH_ENDPOINTS.DETAIL(id)),

  create: (data: BatchCreateRequest) => api.post<Batch>(BATCH_ENDPOINTS.CREATE, data),

  update: (id: string, data: BatchUpdateRequest) =>
    api.patch<Batch>(BATCH_ENDPOINTS.UPDATE(id), data),

  remove: (id: string) => api.delete<OkResponse>(BATCH_ENDPOINTS.DELETE(id)),
}
