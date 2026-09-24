/**
 * Integration domain types — mirror of `backend/app/schemas/integration.py`.
 *
 * The literal unions are the same closed sets the backend declares, so an
 * unknown `location` or `value_source` is a compile error rather than a request
 * the server answers 422 to.
 */

import type { AuditedResource, IntegrationFilterParams, PageParams } from '@/types/api'

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

/** How a body is decoded: an API body, a screen, or a file read in chunks. */
export type ResponseFormat = 'JSON' | 'XML' | 'HTML' | 'CSV'

/** How a portal answers: an API with a JSON/XML body, or a screen behind a session. */
export type Transport = 'HTTP_JSON' | 'HTML_FORM'

/** How a RESPONSE row is read: a pointer into a body, or one of the HTML locators. */
export type LocatorKind = 'POINTER' | 'CSS' | 'LABEL' | 'REGEX' | 'SECTION'

export type HttpMethod = 'GET' | 'HEAD' | 'OPTIONS' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/** How a call ended — `ck_integration_call_outcome`, verbatim. */
export type CallOutcome = 'SUCCESS' | 'REFUSED' | 'TIMEOUT' | 'UNREACHABLE' | 'RATE_LIMITED'

/**
 * One logged external call — mirror of `IntegrationCallReadResponse`.
 *
 * No bodies and no headers: they are stored, scrubbed, for an incident, and a
 * page of twenty rows would otherwise carry twenty provider documents. What a
 * log answers is which operation, when, how long, and whether it came back.
 */
export interface IntegrationCall extends AuditedResource {
  operation_id: string | null
  provider_code: string
  operation_code: string
  method: HttpMethod
  url: string
  status_code: number | null
  outcome: CallOutcome
  duration_ms: number
  attempts: number
  request_id: string | null
  error_code: string | null
  error_detail: string | null
  secret_name: string | null
}

export interface IntegrationSecret extends AuditedResource {
  name: string
  description: string | null
  enabled: boolean
  /** Secrets of one provider sharing a group are one credential: the client rotates. */
  rotation_group: string | null
  /** When a member answered the quota code, plus the window; null when fresh. */
  exhausted_until: string | null
}

export interface IntegrationField extends AuditedResource {
  direction: FieldDirection
  location: FieldLocation
  key: string
  wire_path: string
  locator_kind: LocatorKind
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
  /** Records one window of this operation asks for - the service's measured ceiling. */
  page_size: number
  /** Caller input this feed is addressed by, when the service publishes one set per coordinate. */
  segment_key: string | null
  /** Values that coordinate takes, listed on the row; seeded by migration, read-only here. */
  segment_values: string[] | null
  connect_timeout_ms: number
  read_timeout_ms: number
  max_retries: number
  retry_base_ms: number
  retry_max_ms: number
  idempotent: boolean
  request_schema: Record<string, unknown> | null
  /** Envelope code -> seconds the key sits out; the client tries the next member. */
  quota_codes: Record<string, number>
  enabled: boolean
  fields: IntegrationField[]
}

export interface Integration extends AuditedResource {
  code: string
  display_name: string
  base_url: string
  transport: Transport
  /** The screen that mints the session cookie; only an `HTML_FORM` portal has one. */
  bootstrap_path: string | null
  /** Floor on the gap between two calls to this host, in ms; 0 for an API. */
  min_interval_ms: number
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
  rotation_group?: string | null
}

/** An absent `value` keeps the stored one — the value is write-only. */
export interface IntegrationSecretUpdateRequest {
  value?: string | null
  description?: string | null
  enabled?: boolean | null
  rotation_group?: string | null
}

export interface IntegrationFieldCreateRequest {
  direction: FieldDirection
  location: FieldLocation
  key: string
  wire_path: string
  locator_kind?: LocatorKind
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
  page_size?: number
  connect_timeout_ms: number
  read_timeout_ms: number
  max_retries: number
  retry_base_ms: number
  retry_max_ms: number
  idempotent: boolean
  request_schema?: Record<string, unknown> | null
  quota_codes?: Record<string, number>
  enabled?: boolean
  fields?: IntegrationFieldCreateRequest[]
}

export interface IntegrationCreateRequest {
  code: string
  display_name: string
  base_url: string
  transport?: Transport
  bootstrap_path?: string | null
  min_interval_ms?: number
  enabled?: boolean
  secrets?: IntegrationSecretCreateRequest[]
  operations?: IntegrationOperationCreateRequest[]
}

export interface IntegrationUpdateRequest {
  display_name?: string | null
  base_url?: string | null
  transport?: Transport | null
  bootstrap_path?: string | null
  min_interval_ms?: number | null
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

/**
 * What `GET /integration/` accepts: the page plus one filter per filterable
 * column.
 *
 * The intersection lives with the domain rather than in the shared params type,
 * so an endpoint that takes no filter keeps a params type that matches it.
 */
export type IntegrationListParams = PageParams & IntegrationFilterParams
