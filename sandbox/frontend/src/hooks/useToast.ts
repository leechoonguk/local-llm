/**
 * The app's one notification surface — every outcome a screen reports.
 *
 * A mutation reports through it directly; a failed read reports through
 * `useQueryErrorToast`, which wraps this. Wording and placement are decided
 * once, and screens never call `enqueueSnackbar` directly — that is how three
 * different variants for "saved" appear.
 */

import { useMemo } from 'react'
import { useSnackbar } from 'notistack'

export function useToast() {
  const { enqueueSnackbar } = useSnackbar()

  return useMemo(
    () => ({
      success: (message: string) => enqueueSnackbar(message, { variant: 'success' }),
      error: (message: string) => enqueueSnackbar(message, { variant: 'error' }),
    }),
    [enqueueSnackbar],
  )
}
