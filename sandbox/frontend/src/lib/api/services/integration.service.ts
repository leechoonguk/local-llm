/**
 * Integration service — provider CRUD plus the two child collections the
 * backend exposes (named secrets, operation execution).
 *
 * A secret's value is write-only: `create` sends it, and nothing reads it back
 * (`IntegrationSecretReadResponse` has no `value`).
 */

import { api } from '@/lib/api/client'
import { INTEGRATION_ENDPOINTS } from '@/lib/api/endpoints'
import type { OffsetLimitParams, OkResponse } from '@/types/api'
import type {
  IntegrationExecuteRequest,
  IntegrationExecuteResponse,
  Integration,
  IntegrationCreateRequest,
  IntegrationSecret,
  IntegrationSecretCreateRequest,
  IntegrationSecretUpdateRequest,
  IntegrationUpdateRequest,
} from '@/types/integration'

export const integrationService = {
  list: (params: OffsetLimitParams) =>
    api.get<Integration[]>(INTEGRATION_ENDPOINTS.LIST, { params }),

  detail: (id: string) => api.get<Integration>(INTEGRATION_ENDPOINTS.DETAIL(id)),

  create: (data: IntegrationCreateRequest) =>
    api.post<Integration>(INTEGRATION_ENDPOINTS.CREATE, data),

  update: (id: string, data: IntegrationUpdateRequest) =>
    api.patch<Integration>(INTEGRATION_ENDPOINTS.UPDATE(id), data),

  remove: (id: string) => api.delete<OkResponse>(INTEGRATION_ENDPOINTS.DELETE(id)),

  execute: (id: string, operation: string, data: IntegrationExecuteRequest) =>
    api.post<IntegrationExecuteResponse>(INTEGRATION_ENDPOINTS.EXECUTE(id, operation), data),

  createSecret: (id: string, data: IntegrationSecretCreateRequest) =>
    api.post<IntegrationSecret>(INTEGRATION_ENDPOINTS.SECRETS(id), data),

  /** An absent `value` keeps the stored one — the value is write-only. */
  updateSecret: (id: string, name: string, data: IntegrationSecretUpdateRequest) =>
    api.put<IntegrationSecret>(INTEGRATION_ENDPOINTS.SECRET(id, name), data),

  removeSecret: (id: string, name: string) =>
    api.delete<OkResponse>(INTEGRATION_ENDPOINTS.SECRET(id, name)),
}
