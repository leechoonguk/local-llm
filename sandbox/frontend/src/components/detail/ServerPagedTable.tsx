/**
 * A table over a **server page**: fixed columns, one footer, one empty sentence.
 *
 * `PagedTableSection` is the sibling for a collection already in hand — it owns
 * a section header and an add button, because the tabs it serves author rows.
 * This one shows a log: nothing is created here, the rows arrive one page at a
 * time, and paging is a request rather than a slice.
 *
 * Both tables in the run-history dialog are this component. Written twice
 * instead, the two would have carried the same head, the same fixed layout and
 * the same footer with different columns — and the second one to be edited
 * would have kept the old row height, which is the defect `PagedTableSection`
 * was extracted to end.
 *
 * The expand indicator is the frame's, not the caller's: a row that opens
 * something below the table has to say so before it is clicked, and it must say
 * it the same way everywhere. Passing `expanded` turns the rows into buttons and
 * draws the chevron; omitting it leaves an inert table.
 */

import type { ReactNode } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import Iconify from '@/components/iconify/Iconify'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import { RECORD_SURFACE } from '@/config'
import type { ServerTablePagination } from '@/hooks/useServerTablePage'

const ROW_HEIGHT = RECORD_SURFACE.TABLE_ROW_HEIGHT

/**
 * The chevron's column, in pixels rather than a share: a percentage of a dialog
 * that resizes gave the icon 11px of the 43px it was allotted once the cell's own
 * 16px padding was taken, and the frame's clipping rule then drew an ellipsis
 * beside a half-hidden glyph. This is the icon's width plus the room to centre it.
 */
const EXPAND_COLUMN_WIDTH = 48

/**
 * The chevron cell is named so the clipping rule can exclude it by selector.
 * Declaring `textOverflow: 'clip'` in the cell's own `sx` does not work and does
 * not say it doesn't: `.table td` outranks `.cell`, so the exception loses and
 * the computed style still reads `ellipsis` — measured. The rule that draws the
 * ellipsis is the one that has to spell the exception.
 */
const EXPAND_CELL_CLASS = 'expand-cell'

/**
 * The 48px is the icon's to be centred in, so the cell keeps no padding of its
 * own; MUI's default 16px each side left a 20px glyph visibly off-centre.
 */
const EXPAND_CELL_SX = { px: 0, verticalAlign: 'middle', lineHeight: 0 } as const

interface ServerPagedTableProps<T> {
  columns: TableColumn[]
  rows: T[]
  rowKey: (row: T) => string
  /** The cells in the columns' order; the chevron cell is the frame's. */
  renderCells: (row: T) => ReactNode
  pagination: ServerTablePagination
  /** The sentence shown instead of an empty body. */
  empty: string
  /** Supplied only by a table whose rows open something: draws the chevron. */
  expanded?: (row: T) => boolean
  onRowClick?: (row: T) => void
}

export default function ServerPagedTable<T>({
  columns,
  rows,
  rowKey,
  renderCells,
  pagination,
  empty,
  expanded,
  onRowClick,
}: ServerPagedTableProps<T>) {
  const { t: tCommon } = useTranslation('common')

  if (rows.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        {empty}
      </Typography>
    )
  }

  return (
    <>
      <Table
        size="small"
        sx={{
          tableLayout: 'fixed',
          // The chevron column is excluded by name: an icon is not a value, and
          // clipping one draws an ellipsis beside a half-hidden glyph.
          [`& th:not(.${EXPAND_CELL_CLASS}), & td:not(.${EXPAND_CELL_CLASS})`]: {
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          },
        }}
      >
        <TableHead>
          <TableRow sx={{ height: ROW_HEIGHT }}>
            {expanded !== undefined && (
              <TableCell
                className={EXPAND_CELL_CLASS}
                sx={{ width: EXPAND_COLUMN_WIDTH, ...EXPAND_CELL_SX }}
              />
            )}
            {columns.map((column) => (
              <TableCell key={column.key} align={column.align} sx={{ width: column.width }}>
                <ClippedText text={column.label} />
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={rowKey(row)}
              hover={onRowClick !== undefined}
              selected={expanded?.(row) ?? false}
              onClick={onRowClick === undefined ? undefined : () => onRowClick(row)}
              sx={{ height: ROW_HEIGHT, cursor: onRowClick === undefined ? 'default' : 'pointer' }}
            >
              {expanded !== undefined && (
                <TableCell
                  align="center"
                  className={EXPAND_CELL_CLASS}
                  sx={EXPAND_CELL_SX}
                  aria-label={expanded(row) ? tCommon('actions.collapse') : tCommon('actions.expand')}
                >
                  <Iconify name={expanded(row) ? 'collapse' : 'expand'} />
                </TableCell>
              )}
              {renderCells(row)}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <TablePagination component="div" {...pagination} />
    </>
  )
}
