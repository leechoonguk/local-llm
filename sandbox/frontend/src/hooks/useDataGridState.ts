/**
 * Grid state for a server-paginated list screen.
 *
 * The backend paginates with `offset`/`limit` and returns a bare array — there
 * is no total count anywhere in the API (`app/routers/*.py`). So the grid runs
 * in MUI's *unknown row count* mode: this hook asks for one row more than the
 * page needs, and `usePagedRows` turns that extra row into `hasNextPage`.
 *
 * Sorting is deliberately absent: no list endpoint accepts a sort parameter, so
 * a server sort model here would be a control that changes nothing. The grid
 * sorts the loaded page client-side, which is what it actually does.
 *
 * The grid's own strings come from MUI's locale bundle, keyed off the active
 * i18n language: the footer says "페이지 당 행" in Korean, as the reference
 * application does, instead of leaving one English row inside a Korean screen.
 */

import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { enUS, koKR } from '@mui/x-data-grid/locales'
import type { GridDensity, GridPaginationModel } from '@mui/x-data-grid'
import { DEFAULT_PAGE_SIZE } from '@/config'
import { usePaginationLabels } from '@/hooks/usePaginationLabels'
import type { OffsetLimitParams } from '@/types/api'

interface UseDataGridStateOptions {
  defaultPageSize?: number
  defaultDensity?: GridDensity
  defaultColumnVisibilityModel?: Record<string, boolean>
}

export function useDataGridState(options: UseDataGridStateOptions = {}) {
  const {
    defaultPageSize = DEFAULT_PAGE_SIZE,
    defaultDensity = 'standard',
    defaultColumnVisibilityModel = {},
  } = options

  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: defaultPageSize,
  })
  const [density, setDensity] = useState<GridDensity>(defaultDensity)
  const [columnVisibilityModel, setColumnVisibilityModel] = useState<Record<string, boolean>>(
    defaultColumnVisibilityModel,
  )

  const resetPage = useCallback(() => {
    setPaginationModel((previous) => ({ ...previous, page: 0 }))
  }, [])

  // One row past the page: its presence is the only evidence of a next page an
  // uncounted collection can give.
  const params = useMemo<OffsetLimitParams>(
    () => ({
      offset: paginationModel.page * paginationModel.pageSize,
      limit: paginationModel.pageSize + 1,
    }),
    [paginationModel.page, paginationModel.pageSize],
  )

  const { i18n } = useTranslation()
  const labels = usePaginationLabels()
  /**
   * The bundle is the base, our two strings win. MUI X's koKR is half-translated:
   * `paginationRowsPerPage` is Korean while `paginationDisplayedRows` returns
   * `${from}–${to} of ${count}` — measured as `페이지 당 행: 10  1–2 of 2`. Detail
   * dialogs render a core `TablePagination` from the same two strings, so both
   * footers read alike instead of one page saying `of` and the next `전체`.
   */
  const localeText = useMemo(() => {
    const bundle = i18n.language === 'en' ? enUS : koKR
    return {
      ...bundle.components.MuiDataGrid.defaultProps.localeText,
      paginationRowsPerPage: labels.labelRowsPerPage,
      paginationDisplayedRows: labels.labelDisplayedRows,
    }
  }, [i18n.language, labels])

  return {
    paginationModel,
    setPaginationModel,
    resetPage,
    params,
    density,
    setDensity,
    columnVisibilityModel,
    setColumnVisibilityModel,
    localeText,
  }
}
