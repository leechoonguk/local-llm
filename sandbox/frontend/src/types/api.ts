/**
 * Shared API types — the wire contract every domain type builds on.
 *
 * The shapes here mirror the backend exactly: `AuditedResource` is
 * `AuditMixin` (backend/app/models/base.py), and `ApiErrorBody` is the single
 * error body every handler in `app/core/exceptions.py` returns.
 */

/** Every failure body the backend produces: `detail`, `code`, `request_id`. */
export interface ApiErrorBody {
  detail: string
  code: string
  request_id: string | null
  provider?: string
  operation?: string
  /**
   * What the external provider itself answered, present only when it answered.
   * A timeout and an unreachable host omit it — there is no response to show.
   * `body` is capped and has every sent credential replaced by `***` server-side.
   */
  upstream?: UpstreamResponse
}

/** The provider's own reply, as the integration error handlers expose it. */
export interface UpstreamResponse {
  status_code: number
  body: string | null
}

/**
 * Columns every audited row carries. `version` is the optimistic-lock counter —
 * a stale write answers 409 `stale_version`, which the UI reports as "reload".
 */
export interface AuditedResource {
  id: string
  created_by: string | null
  updated_by: string | null
  created_at: string
  updated_at: string
  version: number
}

/**
 * Pagination the backend actually implements: `offset`/`limit`, no envelope and
 * no total count. A list response is a bare array, so the grid's row count is
 * derived from the page (see `useOffsetPage`), never read from a `total` field
 * that does not exist.
 */
/**
 * One page of a collection — the shape every list endpoint answers with
 * (`backend/app/schemas/page.py`).
 *
 * `total` is the count under the same filter as `items`, without the window, so
 * a footer can say "1–10 of 240" on the first page instead of discovering the
 * number on the last.
 */
export interface Page<T> {
  items: T[]
  total: number
}

export interface OffsetLimitParams {
  offset: number
  limit: number
}

/** `DELETE` endpoints answer `{"ok": true}` rather than 204. */
export interface OkResponse {
  ok: boolean
}
