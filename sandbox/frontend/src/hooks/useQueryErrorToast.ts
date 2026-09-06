/**
 * The app's only way to report a failed read.
 *
 * A failed page used to draw an inline `<Alert>` above the table, which put two
 * failure vocabularies on one screen: a banner for reads, a toast for writes.
 * Both now speak as a toast, and the retry a screen offers is the toolbar's
 * refresh — the only refresh control a list already had.
 *
 * The episode is keyed by `errorUpdatedAt`, not by `isError`. Keyed on the flag,
 * a failed retry said nothing at all: `isError` was already true, so the refresh
 * the user pressed against a dead API produced a request, a spinner and silence
 * (measured on the user list with the backend stopped — the second click drew no
 * toast). Every failed fetch stamps a new time, so every attempt is answered
 * once, and a re-render alone is answered not at all.
 */

import { useEffect, useRef } from 'react'
import { useToast } from '@/hooks/useToast'

interface FailedRead {
  isError: boolean
  errorUpdatedAt: number
}

export function useQueryErrorToast(query: FailedRead, message: string) {
  const toast = useToast()
  const reported = useRef(0)

  useEffect(() => {
    if (!query.isError) return
    if (reported.current === query.errorUpdatedAt) return
    reported.current = query.errorUpdatedAt
    toast.error(message)
  }, [query.isError, query.errorUpdatedAt, message, toast])
}
