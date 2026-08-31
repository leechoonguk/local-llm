/**
 * The one wording for every row footer in the app.
 *
 * Two components render that footer — the list page's `ServerDataGrid` (MUI X)
 * and a detail dialog's `TablePagination` (MUI core) — and neither ships a usable
 * Korean string:
 *
 * - MUI core has no locale bundle wired here, so its defaults are English.
 * - The `@mui/x-data-grid` koKR bundle is half-translated: `paginationRowsPerPage`
 *   is `'페이지 당 행:'` while `paginationDisplayedRows` returns
 *   `` `${from}–${to} of ${count}` `` — measured on the integration list, which
 *   read `페이지 당 행: 10  1–2 of 2`.
 *
 * So the labels come from our own locale files and are handed to both surfaces.
 * A reader moving from a list into a dialog must not have to notice that the
 * footer changed vocabulary.
 */

import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

/** MUI passes `estimated` when the total is a guess; the grid uses -1 for unknown. */
export interface DisplayedRowsInfo {
  from: number
  to: number
  count: number
}

export function usePaginationLabels() {
  const { t } = useTranslation('common')

  return useMemo(
    () => ({
      labelRowsPerPage: t('pagination.rows_per_page'),
      labelDisplayedRows: ({ from, to, count }: DisplayedRowsInfo) =>
        count < 0
          ? t('pagination.displayed_rows_unknown', { from, to })
          : t('pagination.displayed_rows', { from, to, count }),
    }),
    [t],
  )
}
