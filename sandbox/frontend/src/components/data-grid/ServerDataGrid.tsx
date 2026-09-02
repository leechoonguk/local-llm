/**
 * The one grid every list screen renders.
 *
 * It fixes what server pagination against this backend means: `paginationMode`
 * is always `server` and `rowCount` is the total the endpoint returned
 * (`Page<T>`), so the footer reads "1–10 of 240" on the first page. A screen
 * that renders `<DataGrid>` directly re-decides both, so
 * `check-frontend-screens` forbids it outside this file.
 *
 * Appearance and locale live here too — a neutral header strip, dividers under
 * cells, and MUI's own strings in the active language, so the footer never
 * leaves one English row inside a Korean screen. A row being edited carries the
 * amber `warning.lighter` wash: the row is the unit that saves, so the state
 * shown is "this row has unsaved changes", not "this cell has focus". MUI's own
 * editing style is a white cell with a shadow, which is invisible on a white
 * table, so the cell background is cleared for the row wash to show through.
 */

import { useCallback, useMemo } from 'react'
import { alpha } from '@mui/material/styles'
import type { Theme } from '@mui/material/styles'
import { DataGrid } from '@mui/x-data-grid'
import type {
  GridColDef,
  GridDensity,
  GridRenderCellParams,
  GridPaginationModel,
  GridRowModesModel,
  GridValidRowModel,
} from '@mui/x-data-grid'
import { PAGE_SIZE_OPTIONS } from '@/config'
import ClippedText from '@/components/detail/ClippedText'
import DataGridEmptyOverlay from '@/components/data-grid/DataGridEmptyOverlay'

/**
 * The horizontal gutter every cell and header carries, in theme spacing units.
 * A column whose width is computed from its content — the action column — has to
 * add this twice, so it is exported in pixels rather than retyped there: a
 * gutter that disagrees with the grid is how content ends up outside the table.
 */
const CELL_GUTTER = 2.5

export const CELL_GUTTER_PX = CELL_GUTTER * 8

/** The edge bar's width: the state has to survive a screenshot in greyscale. */
const EDIT_MARKER_PX = 3

/**
 * "This row is being edited", for the grid and for a plain `<TableRow>` that
 * edits in place the same way.
 *
 * Not `warning`: amber is this palette's caution — a delete panel's alert, a
 * field whose mapping the server would reject — and a row someone chose to edit
 * is not a caution. Spending the caution colour on an ordinary action leaves
 * nothing louder for a real one. The bar carries the state without hue, so the
 * row survives greyscale and colour-blind vision (WCAG 1.4.1).
 */
export const EDITING_ROW_SX = {
  bgcolor: (theme: Theme) => alpha(theme.palette.primary.main, 0.08),
  boxShadow: (theme: Theme) => `inset ${EDIT_MARKER_PX}px 0 0 0 ${theme.palette.primary.main}`,
} as const

const BASE_SX = {
  border: 'none',
  '--DataGrid-overlayHeight': '320px',
  '& .MuiDataGrid-columnHeader': { px: CELL_GUTTER, bgcolor: 'background.neutral' },
  '& .MuiDataGrid-columnHeaderTitle': { typography: 'subtitle2', color: 'text.secondary' },
  '& .MuiDataGrid-cell': { px: CELL_GUTTER, borderBottom: '1px solid', borderColor: 'divider' },
  // MUI X rings the focused cell on `:focus-within`, so clicking a row's pencil
  // drew a second rectangle around the action buttons while the row already said
  // it was editing. The ring is kept for keyboards, where it is the only cue that
  // says which cell arrow keys will act on, and dropped for the pointer that aimed.
  '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': { outline: 'none' },
  '& .MuiDataGrid-cell:focus-visible': {
    outline: 'solid 1px',
    outlineColor: 'primary.main',
    outlineOffset: '-1px',
  },
  '& .MuiDataGrid-cell button:focus-visible': {
    outline: 'solid 2px',
    outlineColor: 'primary.main',
    outlineOffset: 2,
  },
  '& .MuiDataGrid-row--editing, & .MuiDataGrid-row--editing:hover': EDITING_ROW_SX,
  // MUI's editing style is a white cell with a shadow, invisible on a white table.
  '& .MuiDataGrid-row--editing .MuiDataGrid-cell': { bgcolor: 'transparent', boxShadow: 'none' },
  '& .MuiDataGrid-columnSeparator': { display: 'none' },
  '& .MuiDataGrid-footerContainer': { borderTop: '1px solid', borderColor: 'divider' },
} as const

interface ServerDataGridProps<R extends GridValidRowModel> {
  rows: R[]
  columns: GridColDef<R>[]
  loading: boolean
  rowCount: number
  emptyTitle: string
  localeText: Record<string, unknown>
  paginationModel: GridPaginationModel
  onPaginationModelChange: (model: GridPaginationModel) => void
  density: GridDensity
  columnVisibilityModel: Record<string, boolean>
  onColumnVisibilityModelChange: (model: Record<string, boolean>) => void
  /**
   * Row editing, when a screen edits in place instead of in a dialog. The props
   * are pass-through on purpose: `editMode` is always `row` here, because a
   * half-edited row that saves one cell at a time would send one PUT per cell to
   * an endpoint that takes the whole resource.
   */
  rowModesModel?: GridRowModesModel
  onRowModesModelChange?: (model: GridRowModesModel) => void
  processRowUpdate?: (updated: R, original: R) => Promise<R> | R
  onProcessRowUpdateError?: (error: unknown) => void
}

export default function ServerDataGrid<R extends GridValidRowModel>({
  rows,
  columns,
  loading,
  rowCount,
  emptyTitle,
  localeText,
  paginationModel,
  onPaginationModelChange,
  density,
  columnVisibilityModel,
  onColumnVisibilityModelChange,
  rowModesModel,
  onRowModesModelChange,
  processRowUpdate,
  onProcessRowUpdateError,
}: ServerDataGridProps<R>) {
  const EmptyOverlay = useCallback(() => <DataGridEmptyOverlay title={emptyTitle} />, [emptyTitle])

  /**
   * A clipped value is unreadable until it is hovered, so every text column draws
   * through `ClippedText`, which attaches a real tooltip when the text overflows.
   *
   * The native `title` attribute was the first attempt: the browser draws that
   * tooltip in its own chrome, nothing in the DOM proves it appeared, and from the
   * screen it did not. The wrapper is injected here rather than written per column,
   * because a column that forgets it is a value a reader cannot reach and nothing
   * says so.
   *
   * Skipped where a tooltip would be wrong: a column that renders its own cell (it
   * owns what hovering means — a badge, a count, a switch) and MUI's own
   * `type: 'actions'` column, whose buttons carry their own labels.
   */
  const titled = useMemo(
    () =>
      columns.map((column) =>
        column.renderCell !== undefined || column.type === 'actions'
          ? column
          : {
              ...column,
              renderCell: (params: GridRenderCellParams<R>) => {
                const text = params.formattedValue ?? params.value
                return <ClippedText text={text === null || text === undefined ? '' : String(text)} />
              },
            },
      ),
    [columns],
  )

  const slots = useMemo(
    () => ({ noRowsOverlay: EmptyOverlay, noResultsOverlay: EmptyOverlay }),
    [EmptyOverlay],
  )

  return (
    <DataGrid
      rows={rows}
      columns={titled}
      loading={loading}
      paginationMode="server"
      rowCount={rowCount}
      paginationModel={paginationModel}
      onPaginationModelChange={onPaginationModelChange}
      pageSizeOptions={PAGE_SIZE_OPTIONS}
      localeText={localeText}
      density={density}
      columnVisibilityModel={columnVisibilityModel}
      onColumnVisibilityModelChange={onColumnVisibilityModelChange}
      editMode="row"
      rowModesModel={rowModesModel}
      onRowModesModelChange={onRowModesModelChange}
      processRowUpdate={processRowUpdate}
      onProcessRowUpdateError={onProcessRowUpdateError}
      slots={slots}
      disableColumnFilter
      disableRowSelectionOnClick
      autoHeight
      sx={BASE_SX}
    />
  )
}
