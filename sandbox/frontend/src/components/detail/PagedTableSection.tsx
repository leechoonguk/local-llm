/**
 * A detail dialog's child collection: one titled section, one add button, one
 * fixed-layout table, one footer.
 *
 * The two integration tabs were 83 of 118 lines identical — the same section
 * frame, the same empty sentence, the same `tableLayout: 'fixed'` head and body,
 * the same action cell, the same footer — differing only in which columns they
 * declare and which cells a row draws. That is duplication of the frame, not of
 * the data, so the frame lives here and the callers pass columns and cells.
 *
 * Not a grid: `ServerDataGrid` owns server paging, sorting, density and column
 * visibility for a whole page. This is a nested collection already in hand, drawn
 * as a plain table so a dialog does not carry a grid's chrome.
 */

import type { ReactNode } from 'react'
import ClippedText from '@/components/detail/ClippedText'
import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailSection from '@/components/detail/DetailSection'
import { RowActionButtons } from '@/components/data-grid/RowActions'
import type { RowAction } from '@/components/data-grid/RowActions'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'
import { RECORD_SURFACE } from '@/config'
import type { TablePaging } from '@/hooks/useTablePage'

/**
 * Declared shares, never `auto`: auto layout gave a code column 130px and wrapped
 * every value onto two lines, so one tab's row was 57px against the other's 37px.
 */
export interface TableColumn {
  key: string
  label: string
  /** A percentage, so the columns of two sibling tables read at the same rhythm. */
  width: string
  align?: 'left' | 'center' | 'right'
}

const ROW_HEIGHT = RECORD_SURFACE.TABLE_ROW_HEIGHT

interface PagedTableSectionProps<T> {
  /** The section's icon, the same vocabulary the tab strip uses. */
  icon: ActionIcon
  title: string
  onCreate: () => void
  columns: TableColumn[]
  /** The actions column's share, declared by the caller with the rest. */
  actionsWidth: string
  paging: TablePaging<T>
  rowKey: (row: T) => string
  /** The cells before the action cell, in the columns' order. */
  renderCells: (row: T) => ReactNode
  actions: (row: T) => RowAction[]
}

export default function PagedTableSection<T>({
  icon,
  title,
  onCreate,
  columns,
  actionsWidth,
  paging,
  rowKey,
  renderCells,
  actions,
}: PagedTableSectionProps<T>) {
  const { t: tCommon } = useTranslation('common')
  const { visible, pagination, count } = paging

  return (
    <DetailSection
      name={icon}
      title={title}
      action={
        <Button size="small" startIcon={<Iconify name="add" />} onClick={onCreate}>
          {tCommon('actions.add')}
        </Button>
      }
    >
      {count === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {tCommon('messages.no_data')}
        </Typography>
      ) : (
        <Table
          size="small"
          sx={{
            tableLayout: 'fixed',
            // Fixed shares alone do not clip: the long value — a path template on
            // every row — drew over the next two columns, and a code wrapped onto
            // a second line, making the row 57px against the declared 37. Every
            // cell carries a `title`, so clipped text stays readable on hover.
            '& th, & td': { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
          }}
        >
          <TableHead>
            <TableRow sx={{ height: ROW_HEIGHT }}>
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  align={column.align}
                  sx={{ width: column.width }}
                >
                  <ClippedText text={column.label} />
                </TableCell>
              ))}
              <TableCell align="right" sx={{ width: actionsWidth }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {visible.map((row) => (
              <TableRow key={rowKey(row)} sx={{ height: ROW_HEIGHT }}>
                {renderCells(row)}
                <TableCell align="right">
                  <RowActionButtons actions={actions(row)} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {count > 0 && <TablePagination component="div" {...pagination} />}
    </DetailSection>
  )
}
