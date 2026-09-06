/**
 * The filter state of a list screen: what is typed, what is asked for, and when.
 *
 * A list filters by naming columns — `username`, `code` — and each name is the
 * query parameter the router reads (`TextFilterQuery` in
 * `app/dependencies/query.py`). The hook holds one string per field and answers
 * with `params`: the fields that have a value, omitted entirely when they do
 * not. An empty box is never sent as `field=`, because the backend declares
 * `min_length=1` and would answer 422 for a screen the reader thinks is
 * unfiltered.
 *
 * Two behaviours it owns, because both were written per screen and both are the
 * kind of thing that drifts:
 *
 *   - **Debounce.** Every keystroke is a query key, so an undebounced field
 *     sends one request per character and the answers can land out of order —
 *     "ali" arriving after "alic" shows rows the boxes no longer describe.
 *   - **Page reset.** A filter that matches three rows while the grid sits on
 *     page 4 answers an empty page, which reads as "no results" for a filter
 *     that has them. `onApply` is the screen's `resetPage`.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

/** How long typing rests before a filter becomes a request. */
const FILTER_DEBOUNCE_MS = 300

const emptyValues = <F extends string>(fields: readonly F[]): Record<F, string> =>
  Object.fromEntries(fields.map((field) => [field, ''])) as Record<F, string>

export function useListFilters<F extends string>(fields: readonly F[], onApply: () => void) {
  const [inputs, setInputs] = useState<Record<F, string>>(() => emptyValues(fields))
  const [applied, setApplied] = useState<Record<F, string>>(() => emptyValues(fields))

  const setInput = useCallback((field: F, value: string) => {
    setInputs((previous) => ({ ...previous, [field]: value }))
  }, [])

  const reset = useCallback(() => setInputs(emptyValues(fields)), [fields])

  useEffect(() => {
    const timer = setTimeout(() => {
      setApplied(
        Object.fromEntries(
          Object.entries(inputs).map(([field, value]) => [field, String(value).trim()]),
        ) as Record<F, string>,
      )
      onApply()
    }, FILTER_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [inputs, onApply])

  const params = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(applied).filter(([, value]) => value !== ''),
      ) as Partial<Record<F, string>>,
    [applied],
  )

  const isFiltered = useMemo(
    () => Object.values(inputs).some((value) => String(value) !== ''),
    [inputs],
  )

  return { inputs, setInput, reset, params, isFiltered }
}
