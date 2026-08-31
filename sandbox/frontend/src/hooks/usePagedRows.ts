/**
 * Turns a peeked page into grid rows, a row count and `paginationMeta`.
 *
 * `useDataGridState` asks for `pageSize + 1` rows. The extra row never reaches
 * the grid; it only answers "is there a next page".
 *
 * Two values come out of that answer, because MUI needs both:
 *
 *   `rowCount` — exact once the peek came back short: the collection ends on
 *   this page, so the total is `offset + rows.length`. Reporting `-1` there
 *   leaves the footer claiming "1–10 of more than 10" over two rows.
 *   `paginationMeta` — the unknown-count fallback while more pages may exist.
 *
 * `paginationMeta` must not go back to `undefined` while paging: MUI resets the
 * page to zero when it does (MUI X pagination docs), which is why the published
 * pattern parks it in a ref. Here the guarantee comes from the query layer
 * instead — every list hook declares `placeholderData: (previous) => previous`,
 * so `data` keeps the previous page during a fetch and `hasNextPage` is only
 * `undefined` before the very first response. `check-frontend-api-layer`
 * enforces that declaration, so this stays a pure derivation.
 */

import { useMemo } from 'react'
import type { GridPaginationMeta } from '@mui/x-data-grid'

/** MUI's sentinel for "the total is unknown, ask `paginationMeta` instead". */
export const UNKNOWN_ROW_COUNT = -1

export function usePagedRows<T>(data: T[] | undefined, page: number, pageSize: number) {
  const hasNextPage = data === undefined ? undefined : data.length > pageSize

  const paginationMeta = useMemo<GridPaginationMeta | undefined>(
    () => (hasNextPage === undefined ? undefined : { hasNextPage }),
    [hasNextPage],
  )

  const rows = useMemo(() => (data ?? []).slice(0, pageSize), [data, pageSize])

  const rowCount = hasNextPage === false ? page * pageSize + rows.length : UNKNOWN_ROW_COUNT

  return { rows, rowCount, paginationMeta }
}
