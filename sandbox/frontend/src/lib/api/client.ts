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

/** Login itself answers 401 for bad credentials — that is not an expired session. */
const AUTH_PATHS = ['/auth/login']

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token !== null) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const apiError = toApiError(error)
    const url = axios.isAxiosError(error) ? (error.config?.url ?? '') : ''
    const isAuthRequest = AUTH_PATHS.some((path) => url.startsWith(path))
    if (apiError.status === 401 && !isAuthRequest) {
      setAccessToken(null)
      emitSessionExpired()
    }
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
