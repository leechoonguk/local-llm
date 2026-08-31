/**
 * Server refusals, translated and shown where the user can act on them.
 *
 * The backend answers every failure with `{ detail, code, request_id }`. `detail`
 * is English written for a log line; the sentence a user reads comes from
 * `locales/*.ts` keyed by `code`, because the server does not know which
 * language this session speaks.
 *
 * Two behaviours, both measured as missing: a dialog used to swallow every
 * failure into one generic "저장 실패", so adding a provider whose code was taken
 * said nothing about the code — the only way to learn the cause was the network
 * tab. And a naive fix (`toast.error(apiError.message)`) ships English into a
 * Korean screen.
 */

import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import { toApiError } from '@/lib/api/errors'

/** The message for a failure that never reached a handler, so it has no code. */
const FALLBACK_KEY = 'errors.unknown'

type Translator = (key: string) => string

/**
 * Translate one failure. `fieldByCode` lets a dialog put the message on the
 * input that owns it — a taken provider code is a fact about the `code` field —
 * and anything unclaimed becomes a toast.
 */
export function applyServerError<T extends FieldValues>(
  error: unknown,
  options: {
    t: Translator
    setError: UseFormSetError<T>
    toastError: (message: string) => void
    fieldByCode?: Partial<Record<string, Path<T>>>
  },
): void {
  const { t, setError, toastError, fieldByCode = {} } = options
  const apiError = toApiError(error)
  const message = serverErrorMessage(apiError.code, t)
  const field = fieldByCode[apiError.code]

  if (field !== undefined) {
    setError(field, { type: 'server', message })
    return
  }
  toastError(message)
}

/**
 * The translated sentence for one server code.
 *
 * An unknown code falls back rather than rendering the raw code: a new backend
 * failure mode is caught by `check-frontend-i18n` at build time, so the fallback
 * is for a version skew between a deployed client and a newer server.
 */
export function serverErrorMessage(code: string, t: Translator): string {
  const key = `errors.${code}`
  const message = t(key)

  return message === key ? t(FALLBACK_KEY) : message
}
