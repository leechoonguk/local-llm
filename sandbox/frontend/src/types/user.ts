/**
 * User domain types — mirror of `backend/app/schemas/user.py`.
 *
 * One TS type per Pydantic request/response class, field for field. The
 * `check-frontend-contract` hook compares these declarations against the
 * backend schema, so a field added on the server fails the build here.
 */

import type { AuditedResource } from '@/types/api'

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
