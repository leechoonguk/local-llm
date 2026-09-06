/**
 * User domain types — mirror of `backend/app/schemas/user.py`.
 *
 * One TS type per Pydantic request/response class, field for field. The
 * `check-frontend-contract` hook compares these declarations against the
 * backend schema, so a field added on the server fails the build here.
 */

import type { AuditedResource, OffsetLimitParams, UserFilterParams } from '@/types/api'

export interface User extends AuditedResource {
  username: string
  email: string
}

export interface UserCreateRequest {
  username: string
  email: string
  password: string
}

export interface UserUpdateRequest {
  username?: string
  email?: string
  password?: string
}

/**
 * What `GET /user/` accepts: the page plus one filter per filterable column.
 *
 * The user list is the only screen that filters today, so the intersection
 * lives here rather than in the shared params type — a domain that gains
 * filters declares its own, and one that never does keeps a params type that
 * matches its endpoint.
 */
export type UserListParams = OffsetLimitParams & UserFilterParams
