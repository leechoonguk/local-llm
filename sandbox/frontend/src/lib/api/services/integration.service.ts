/**
 * Integration service — provider CRUD plus the child collections the backend
 * exposes (named secrets, operation execution, and the call log those
 * executions leave behind).
 *
 * A secret's value is write-only: `create` sends it, and nothing reads it back
 * (`IntegrationSecretReadResponse` has no `value`).
 */

import { EXECUTE_TIMEOUT_MS } from '@/config'
import { api } from '@/lib/api/client'
import { INTEGRATION_ENDPOINTS } from '@/lib/api/endpoints'
import type { OkResponse, Page } from '@/types/api'
import type { OffsetLimitParams } from '@/types/api'
import type {
  IntegrationCall,
  IntegrationExecuteRequest,
  IntegrationExecuteResponse,
  Integration,
  IntegrationCreateRequest,
  IntegrationListParams,
  IntegrationSecret,
  IntegrationSecretCreateRequest,
  IntegrationSecretUpdateRequest,
  IntegrationUpdateRequest,
} from '@/types/integration'

export const integrationService = {
  list: (params: IntegrationListParams) =>
    api.get<Page<Integration>>(INTEGRATION_ENDPOINTS.LIST, { params }),

  detail: (id: string) => api.get<Integration>(INTEGRATION_ENDPOINTS.DETAIL(id)),

  create: (data: IntegrationCreateRequest) =>
    api.post<Integration>(INTEGRATION_ENDPOINTS.CREATE, data),

  update: (id: string, data: IntegrationUpdateRequest) =>
    api.patch<Integration>(INTEGRATION_ENDPOINTS.UPDATE(id), data),

  remove: (id: string) => api.delete<OkResponse>(INTEGRATION_ENDPOINTS.DELETE(id)),

  execute: (id: string, operation: string, data: IntegrationExecuteRequest) =>
    api.post<IntegrationExecuteResponse>(INTEGRATION_ENDPOINTS.EXECUTE(id, operation), data, {
      timeout: EXECUTE_TIMEOUT_MS,
    }),

  createSecret: (id: string, data: IntegrationSecretCreateRequest) =>
    api.post<IntegrationSecret>(INTEGRATION_ENDPOINTS.SECRETS(id), data),

  /** An absent `value` keeps the stored one — the value is write-only. */
  updateSecret: (id: string, name: string, data: IntegrationSecretUpdateRequest) =>
    api.put<IntegrationSecret>(INTEGRATION_ENDPOINTS.SECRET(id, name), data),

  removeSecret: (id: string, name: string) =>
    api.delete<OkResponse>(INTEGRATION_ENDPOINTS.SECRET(id, name)),

  /** This provider's calls, newest first — the evidence its operations ran. */
  calls: (id: string, params: OffsetLimitParams) =>
    api.get<Page<IntegrationCall>>(INTEGRATION_ENDPOINTS.CALLS(id), { params }),
}
