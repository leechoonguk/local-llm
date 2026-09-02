/**
 * User service — one function per backend endpoint, no more.
 *
 * A service is transport only: it names the endpoint, passes the params and
 * returns the typed body. Caching, invalidation and toasts belong to the hooks
 * layer, so the same call is reusable from anywhere.
 */

import { api } from '@/lib/api/client'
import { USER_ENDPOINTS } from '@/lib/api/endpoints'
import type { OffsetLimitParams, OkResponse, Page } from '@/types/api'
import type { User, UserCreateRequest, UserUpdateRequest } from '@/types/user'

export const userService = {
  list: (params: OffsetLimitParams) => api.get<Page<User>>(USER_ENDPOINTS.LIST, { params }),

  detail: (id: string) => api.get<User>(USER_ENDPOINTS.DETAIL(id)),

  create: (data: UserCreateRequest) => api.post<User>(USER_ENDPOINTS.CREATE, data),

  update: (id: string, data: UserUpdateRequest) => api.patch<User>(USER_ENDPOINTS.UPDATE(id), data),

  remove: (id: string) => api.delete<OkResponse>(USER_ENDPOINTS.DELETE(id)),
}
