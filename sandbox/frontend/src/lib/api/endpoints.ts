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
  RUN: (id: string) => `/batch/${id}/run`,
  RUNS: (id: string) => `/batch/${id}/runs`,
  RUN_STEPS: (batchId: string, runId: string) => `/batch/${batchId}/runs/${runId}/steps`,
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
  CALLS: (id: string) => `/integration/${id}/calls`,
} as const

export const FOOD_ENDPOINTS = {
  ITEM_REPORT_LIST: '/food/item-report/',
  SAFETY_RECORD_LIST: '/food/safety-record/',
  SAFETY_RECORD_FACETS: '/food/safety-record/facets',
  ITEM_REPORT_FACETS: '/food/item-report/facets',
  ITEM_REPORT_DETAIL: (id: string) => `/food/item-report/${id}`,
  ITEM_REPORT_DECLARATIONS: (id: string) => `/food/item-report/${id}/declarations`,
  ITEM_REPORT_SAFETY_RECORDS: (id: string) => `/food/item-report/${id}/safety-records`,
  ITEM_REPORT_STANDARDS: (id: string) => `/food/item-report/${id}/standards`,
  ITEM_REPORT_LABELS: (id: string) => `/food/item-report/${id}/labels`,
  RAW_MATERIAL_LIST: '/food/raw-material/',
  RAW_MATERIAL_FACETS: '/food/raw-material/facets',
  RAW_MATERIAL_DETAIL: (id: string) => `/food/raw-material/${id}`,
  RAW_MATERIAL_ITEM_REPORTS: (id: string) => `/food/raw-material/${id}/item-reports`,
  BUSINESS_LIST: '/food/business/',
  BUSINESS_FACETS: '/food/business/facets',
  BUSINESS_DETAIL: (id: string) => `/food/business/${id}`,
  CHAT: '/food/chat',
} as const
