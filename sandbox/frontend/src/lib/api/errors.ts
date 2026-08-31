/**
 * Error normalisation — one `ApiError` for every failure the UI can see.
 *
 * The backend answers every failure with the same body (`detail`, `code`,
 * `request_id`), so the UI never inspects `AxiosError` shapes: interceptors
 * convert once, here, and screens read `error.message` / `error.code`.
 */

import axios from 'axios'
import type { ApiErrorBody, UpstreamResponse } from '@/types/api'

/** A network failure never reached a handler, so it has no server code. */
const NETWORK_ERROR_CODE = 'network_error'

const UNKNOWN_ERROR_CODE = 'unknown_error'

/** Optimistic-lock miss: the row moved under the edit, so reloading is the fix. */
export const STALE_VERSION_CODE = 'stale_version'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  /**
   * The provider's own answer, when the failure was an external call and the
   * provider answered. The screen prints it: the mapped sentence says a call
   * failed, and only this says what came back.
   */
  readonly upstream: UpstreamResponse | null

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
    upstream: UpstreamResponse | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.upstream = upstream
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const body = error.response?.data
    if (error.response === undefined) {
      return new ApiError(0, NETWORK_ERROR_CODE, error.message, null)
    }
    return new ApiError(
      error.response.status,
      body?.code ?? UNKNOWN_ERROR_CODE,
      body?.detail ?? error.message,
      body?.request_id ?? null,
      body?.upstream ?? null,
    )
  }

  const message = error instanceof Error ? error.message : String(error)
  return new ApiError(0, UNKNOWN_ERROR_CODE, message, null)
}
