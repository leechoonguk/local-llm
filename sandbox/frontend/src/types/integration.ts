/**
 * Integration domain types — mirror of `backend/app/schemas/integration.py`.
 *
 * The literal unions are the same closed sets the backend declares, so an
 * unknown `location` or `value_source` is a compile error rather than a request
 * the server answers 422 to.
 */

import type { AuditedResource } from '@/types/api'

export type FieldDirection = 'REQUEST' | 'RESPONSE'

export type FieldLocation = 'PATH' | 'PATH_QUERY' | 'QUERY' | 'HEADER' | 'BODY' | 'ENVELOPE'

export type RequestValueSource = 'CALLER' | 'LITERAL' | 'SECRET' | 'CONTEXT'

export type ValueType =
  | 'STRING'
  | 'INTEGER'
  | 'NUMBER'
  | 'BOOLEAN'
  | 'DATE'
  | 'DATETIME'
  | 'JSON'
  | 'EPOCH_SECONDS'
  | 'HTTP_DATE'
  | 'DURATION_SECONDS'

export type HeaderMatchMode = 'IGNORE' | 'PRESENT' | 'EXACT' | 'ONE_OF'

export type ResponseFormat = 'JSON' | 'XML'

export type HttpMethod = 'GET' | 'HEAD' | 'OPTIONS' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface IntegrationSecret extends AuditedResource {
  name: string
  description: string | null
  enabled: boolean
}

export interface IntegrationField extends AuditedResource {
  direction: FieldDirection
  location: FieldLocation
  key: string
  wire_path: string
  value_source: RequestValueSource | null
  value: unknown
  secret_name: string | null
  value_type: ValueType
  format: string | null
  required: boolean
  description: string | null
  sensitive: boolean
  ordinal: number
  enabled: boolean
  match_mode: HeaderMatchMode | null
  expected_values: string[] | null
}

export interface IntegrationOperation extends AuditedResource {
  code: string
  method: string
  path_template: string
  request_media_type: string | null
  response_format: ResponseFormat
  response_root: string | null
  connect_timeout_ms: number
  read_timeout_ms: number
  max_retries: number
  retry_base_ms: number
  retry_max_ms: number
  idempotent: boolean
  request_schema: Record<string, unknown> | null
  enabled: boolean
  fields: IntegrationField[]
}

export interface Integration extends AuditedResource {
  code: string
  display_name: string
  base_url: string
  enabled: boolean
  secrets: IntegrationSecret[]
  operations: IntegrationOperation[]
}

/**
 * Request models, mirrored field for field from `schemas/integration.py`.
 *
 * The nested trees are here because the server accepts them: a client type that
 * declared only the fields today's screens fill could not express an operation
 * edit, and nothing would say so until someone tried. The backend is the
 * canonical shape, so `check-frontend-types` compares these both ways.
 */
export interface IntegrationSecretCreateRequest {
  name: string
  value: string
  description?: string | null
  enabled?: boolean
}

/** An absent `value` keeps the stored one — the value is write-only. */
export interface IntegrationSecretUpdateRequest {
  value?: string | null
  description?: string | null
  enabled?: boolean | null
}

export interface IntegrationFieldCreateRequest {
  direction: FieldDirection
  location: FieldLocation
  key: string
  wire_path: string
  value_source?: RequestValueSource | null
  value?: unknown
  secret_name?: string | null
  value_type: ValueType
  format?: string | null
  required: boolean
  description?: string | null
  sensitive?: boolean
  ordinal?: number
  enabled?: boolean
  match_mode?: HeaderMatchMode | null
  expected_values?: string[] | null
}

export interface IntegrationOperationCreateRequest {
  code: string
  method: HttpMethod
  path_template: string
  request_media_type?: string | null
  response_format?: ResponseFormat
  response_root?: string | null
  connect_timeout_ms: number
  read_timeout_ms: number
  max_retries: number
  retry_base_ms: number
  retry_max_ms: number
  idempotent: boolean
  request_schema?: Record<string, unknown> | null
  enabled?: boolean
  fields?: IntegrationFieldCreateRequest[]
}

export interface IntegrationCreateRequest {
  code: string
  display_name: string
  base_url: string
  enabled?: boolean
  secrets?: IntegrationSecretCreateRequest[]
  operations?: IntegrationOperationCreateRequest[]
}

export interface IntegrationUpdateRequest {
  display_name?: string | null
  base_url?: string | null
  enabled?: boolean | null
  operations?: IntegrationOperationCreateRequest[] | null
}

export interface IntegrationExecuteRequest {
  inputs: Record<string, unknown>
}

export interface IntegrationExecuteResponse {
  canonical_payload: Record<string, unknown> | unknown[]
  metadata: Record<string, unknown>
  status_code: number
}
