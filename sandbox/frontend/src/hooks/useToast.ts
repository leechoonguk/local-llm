/**
 * The app's only way to report the outcome of a mutation.
 *
 * Every screen reports success and failure the same way, so the wording and
 * the placement are decided once. Screens never call `enqueueSnackbar`
 * directly — that is how three different variants for "saved" appear.
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
