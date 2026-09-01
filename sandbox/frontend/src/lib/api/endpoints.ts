/**
 * Every backend path, in one place.
 *
 * A URL literal inside a service or a screen is a path that no longer matches
 * the router when the backend moves it. `check-frontend-contract` compares this
 * table against `backend/app/routers/*.py`, so a renamed prefix fails a check
 * instead of a request.
 */

export const AUTH_ENDPOINTS = {
  LOGIN: '/auth/login',
  REFRESH: '/auth/refresh',
  LOGOUT: '/auth/logout',
  ME: '/auth/me',
} as const

export const USER_ENDPOINTS = {
  LIST: '/user/',
  CREATE: '/user/',
  DETAIL: (id: string) => `/user/${id}`,
  UPDATE: (id: string) => `/user/${id}`,
  DELETE: (id: string) => `/user/${id}`,
} as const

export const BATCH_ENDPOINTS = {
  LIST: '/batch/',
  CREATE: '/batch/',
  DETAIL: (id: string) => `/batch/${id}`,
  UPDATE: (id: string) => `/batch/${id}`,
  DELETE: (id: string) => `/batch/${id}`,
} as const

export const INTEGRATION_ENDPOINTS = {
  LIST: '/integration/',
  CREATE: '/integration/',
  DETAIL: (id: string) => `/integration/${id}`,
  UPDATE: (id: string) => `/integration/${id}`,
  DELETE: (id: string) => `/integration/${id}`,
  EXECUTE: (id: string, operation: string) =>
    `/integration/${id}/operations/${operation}/execute`,
  SECRETS: (id: string) => `/integration/${id}/secrets`,
  SECRET: (id: string, name: string) => `/integration/${id}/secrets/${name}`,
} as const
