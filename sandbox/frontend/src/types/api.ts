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

/**
 * The page plus the one sorted column: `sort` is a column the router's
 * `<Domain>SortQuery` Literal closes, `order` the `OrderQuery` pair. Both
 * omitted on an unsorted grid, so the endpoint pages by its own order.
 */
export interface PageParams extends OffsetLimitParams {
  sort?: string
  order?: 'asc' | 'desc'
}

/**
 * A list's field filters, one interface per domain, kept apart from
 * `OffsetLimitParams` on purpose.
 *
 * One optional field per filterable column, named exactly as the query
 * parameter (`TextFilterQuery` in `app/dependencies/query.py`) — so a reader
 * sees which column each box narrows instead of guessing what a combined
 * keyword covers. Folding them into the pagination params would put every
 * domain's fields on every list call, including the endpoints that answer 422
 * for them.
 *
 * They live here rather than in `types/<domain>.ts` because
 * `check-frontend-types` reads this file to prove every query parameter the
 * routers declare has a field a caller can send.
 *
 * Every field is omitted rather than sent empty — the backend declares
 * `min_length=1`, so `field=` is a 422, not "no filter".
 */
export interface UserFilterParams {
  username?: string
  email?: string
}

export interface BatchFilterParams {
  name?: string
}

export interface IntegrationFilterParams {
  code?: string
  display_name?: string
}

export interface FoodItemReportFilterParams {
  report_kind?: string
  item_report_no?: string
  license_no?: string
  business_name?: string
  product_name?: string
  product_type_name?: string
  /** Only the products something was published about - 161 of 1.07M domestic rows. */
  has_events?: string
}

export interface FoodRawMaterialFilterParams {
  raw_material_code?: string
  representative_raw_material_name?: string
  raw_material_alias?: string
  raw_material_large_class?: string
  raw_material_medium_class?: string
  raw_material_status_code_name?: string
  use_yn?: string
}

export interface FoodBusinessFilterParams {
  business_name?: string
  license_no?: string
  district?: string
  industry_name?: string
  /** Which ledger the row came from - `ACTIVE` master, `CLOSED` closure feed. */
  status?: string
}

/** `DELETE` endpoints answer `{"ok": true}` rather than 204. */
export interface OkResponse {
  ok: boolean
}
