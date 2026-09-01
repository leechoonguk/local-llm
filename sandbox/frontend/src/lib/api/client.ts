/**
 * The single HTTP client. Every request in the app goes through it.
 *
 * Three things happen here and nowhere else: the bearer token is attached, a
 * 401 clears the session, and every failure becomes an `ApiError`. A screen
 * that builds its own `axios.create()` (or calls `fetch`) skips all three, so
 * `check-frontend-api-layer` forbids it.
 */

import axios from 'axios'
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { API_BASE_URL, API_TIMEOUT_MS } from '@/config'
import { toApiError } from '@/lib/api/errors'
import { emitSessionExpired, getAccessToken, setAccessToken } from '@/lib/api/token'

/**
 * 401s that mean what they say, not an expired session: login is bad
 * credentials, refresh is the session ending (retrying it with itself would
 * recurse), logout is already-out.
 */
const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout']

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
  // The refresh credential is an httpOnly cookie scoped to /api/v1/auth —
  // without credentials the browser never attaches it and every refresh 401s.
  withCredentials: true,
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token !== null) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * The transport for spending the session cookie is injected by `AuthProvider`
 * (it is `authService.refresh` — transport lives in the service layer, and this
 * module cannot import a service that imports it back). Until something
 * registers, a 401 simply ends the session, same as before the feature existed.
 */
type SessionRefresher = () => Promise<string>

let sessionRefresher: SessionRefresher | null = null

export function setSessionRefresher(refresher: SessionRefresher): void {
  sessionRefresher = refresher
}

/**
 * One refresh at a time: a burst of 401s (a screen firing three requests as a
 * token dies) must spend the cookie once — rotation makes the second concurrent
 * refresh a theft signature that kills the whole session.
 */
let refreshInFlight: Promise<string> | null = null

function refreshAccessToken(): Promise<string> {
  if (sessionRefresher === null) {
    return Promise.reject(new Error('no session refresher registered'))
  }
  refreshInFlight ??= sessionRefresher().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retriedAfterRefresh?: boolean
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    const apiError = toApiError(error)
    const config = axios.isAxiosError(error) ? (error.config as RetryableConfig | undefined) : undefined
    const url = config?.url ?? ''
    const isAuthRequest = AUTH_PATHS.some((path) => url.startsWith(path))
    if (apiError.status !== 401 || isAuthRequest) {
      return Promise.reject(apiError)
    }
    // One retry per request: the cookie may still buy a new access token, and
    // the user should never see a session end the server can still avert.
    if (config !== undefined && config._retriedAfterRefresh !== true) {
      try {
        const token = await refreshAccessToken()
        setAccessToken(token)
        config._retriedAfterRefresh = true
        return await apiClient.request(config)
      } catch {
        // fall through — the session is genuinely over
      }
    }
    setAccessToken(null)
    emitSessionExpired()
    return Promise.reject(apiError)
  },
)

/**
 * Typed verb helpers. They exist so a service reads as one line per endpoint and
 * never repeats `.then((res) => res.data)` — the unwrap is the contract, not a
 * detail each service re-decides.
 */
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) =>
    apiClient.get<T>(url, config).then((res) => res.data),

  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    apiClient.post<T>(url, data, config).then((res) => res.data),

  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    apiClient.put<T>(url, data, config).then((res) => res.data),

  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    apiClient.patch<T>(url, data, config).then((res) => res.data),

  delete: <T>(url: string, config?: AxiosRequestConfig) =>
    apiClient.delete<T>(url, config).then((res) => res.data),
}
