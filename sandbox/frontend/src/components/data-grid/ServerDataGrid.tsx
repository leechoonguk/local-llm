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
import type { RefObject } from 'react'
import { alpha } from '@mui/material/styles'
import type { Theme } from '@mui/material/styles'
import { DataGrid, GridRowEditStopReasons, GridRowModes } from '@mui/x-data-grid'
import type { GridApiCommunity } from '@mui/x-data-grid/internals'
import type {
  GridColDef,
  GridRowParams,
  GridDensity,
  GridRenderCellParams,
  GridPaginationModel,
  GridSortModel,
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
  // MUI closes each row with an empty filler cell that holds no value and is
  // meant to take whatever width is left - zero when the columns already fill
  // the row. It is a `.MuiDataGrid-cell` too, so the gutter above gave it a
  // 40px floor it could not shrink below, and every grid in the app reported
  // 40px of content past its own width: a horizontal scrollbar offering empty
  // space. Measured on /batch: virtualScroller 1,120 wide inside 1,080.
  '& .MuiDataGrid-cellEmpty': { px: 0 },
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
  /**
   * Every editable cell carries the same underline, drawn here rather than by
   * each column's editor.
   *
   * A cell has no border of its own to say "type here", and MUI's default input
   * has none either: the row wash said the *row* was open while nothing said
   * which cells took a value. Per-column editors would each redraw it and drift
   * — the user list's password cell already had an underline the columns beside
   * it did not.
   *
   * Three states, all from the palette: resting is the table's own divider,
   * focus is the primary that marks the row, invalid is the error colour the
   * blocked save names in words.
   */
  '& .MuiDataGrid-cell--editing .MuiInputBase-input': {
    borderBottom: '1px solid',
    borderColor: 'divider',
    transition: (theme: Theme) => theme.transitions.create('border-color'),
  },
  '& .MuiDataGrid-cell--editing .MuiInputBase-root.Mui-focused .MuiInputBase-input': {
    borderColor: 'primary.main',
  },
  '& .MuiDataGrid-cell--editing .MuiInputBase-root.Mui-error .MuiInputBase-input': {
    borderColor: 'error.main',
  },
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
  /**
   * The header's sort is the server's: one column at a time, sent as `sort`
   * and `order`, and the page comes back already in that order. A grid that
   * sorted the loaded page itself showed ten rows in order and called it the
   * collection (measured on every list before the model was wired through).
   */
  sortModel: GridSortModel
  onSortModelChange: (model: GridSortModel) => void
  /**
   * True while the page in flight has not landed. Paging and sorting both
   * ask for a different page under the same filters - clicking either again
   * before the first answer lands races two responses for the footer's total
   * and the rows shown; `loading` already names that window, so it disables
   * the pagination controls and the column headers' sort along with it.
   */
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
  /**
   * The grid's own api, for a screen that has to read a row *while* it is being
   * edited — validating on save is the case: the pending values live in the
   * grid's edit state, not in `rows`, so a screen without this can only watch
   * the commit silently fail.
   */
  apiRef?: RefObject<GridApiCommunity | null>
  processRowUpdate?: (updated: R, original: R) => Promise<R> | R
  onProcessRowUpdateError?: (error: unknown) => void
  /**
   * The row as a door. A derived list opens its record dialog from the row
   * itself; a list that edits in place may carry one too, because the door is
   * guarded here rather than by each screen — see `handleRowClick`. The pointer
   * says so while the prop is set.
   */
  onRowClick?: (row: R) => void
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
  sortModel,
  onSortModelChange,
  density,
  columnVisibilityModel,
  onColumnVisibilityModelChange,
  rowModesModel,
  onRowModesModelChange,
  apiRef,
  processRowUpdate,
  onProcessRowUpdateError,
  onRowClick,
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

  /**
   * A click lands on exactly one meaning.
   *
   * Two collisions make that a guard rather than a prop the screen passes
   * through. A row being typed into must not answer a click with a dialog — the
   * pointer is there to reach a cell — so a row in edit mode has no door. And a
   * click inside the actions cell belongs to the button under it: MUI reports a
   * row click for it too, so opening a record on the way to `삭제` would put a
   * dialog over the confirm.
   */
  const handleRowClick = useCallback(
    (params: GridRowParams<R>, event: { target: EventTarget | null }) => {
      if (onRowClick === undefined) return
      if (rowModesModel?.[params.id]?.mode === GridRowModes.Edit) return
      const target = event.target instanceof Element ? event.target : null
      if (target !== null && target.closest('[data-field="actions"]') !== null) return
      onRowClick(params.row)
    },
    [onRowClick, rowModesModel],
  )

  const sx = useMemo(
    () => (onRowClick === undefined ? BASE_SX : { ...BASE_SX, '& .MuiDataGrid-row': { cursor: 'pointer' } }),
    [onRowClick],
  )

  return (
    <DataGrid
      rows={rows}
      columns={titled}
      loading={loading}
      paginationMode="server"
      sortingMode="server"
      sortModel={sortModel}
      onSortModelChange={onSortModelChange}
      disableColumnSorting={loading}
      slotProps={{ basePagination: { disabled: loading } }}
      rowCount={rowCount}
      paginationModel={paginationModel}
      onPaginationModelChange={onPaginationModelChange}
      pageSizeOptions={PAGE_SIZE_OPTIONS}
      localeText={localeText}
      density={density}
      columnVisibilityModel={columnVisibilityModel}
      onColumnVisibilityModelChange={onColumnVisibilityModelChange}
      apiRef={apiRef}
      editMode="row"
      /**
       * A row saves when someone says save, never when focus leaves it.
       *
       * MUI's default stops row editing on `rowFocusOut` and **commits**, so
       * clicking the row's own cancel button first blurred the cell and sent the
       * write the click was there to abort: measured on the user list, where
       * cancelling a new row POSTed the empty draft and answered 422.
       */
      onRowEditStop={(params, event) => {
        if (params.reason === GridRowEditStopReasons.rowFocusOut) {
          event.defaultMuiPrevented = true
        }
      }}
      rowModesModel={rowModesModel}
      onRowModesModelChange={onRowModesModelChange}
      processRowUpdate={processRowUpdate}
      onProcessRowUpdateError={onProcessRowUpdateError}
      slots={slots}
      onRowClick={onRowClick === undefined ? undefined : handleRowClick}
      /**
       * Editing starts at the row's own button when the row is also a door.
       * MUI's default opens an editor on cell double-click, and the first of
       * those two clicks had already opened the dialog — so the second landed on
       * a grid behind it.
       */
      onCellDoubleClick={(_params, event) => {
        if (onRowClick !== undefined) event.defaultMuiPrevented = true
      }}
      disableColumnFilter
      disableRowSelectionOnClick
      autoHeight
      sx={sx}
    />
  )
}
