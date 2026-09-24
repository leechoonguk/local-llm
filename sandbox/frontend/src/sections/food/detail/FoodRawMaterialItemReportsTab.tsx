/**
 * The products whose label names this material - the derive job resolved each
 * ingredient name to a registry code at write time, and this is that edge
 * read back: one row per product, however many times its label repeats the name.
 *
 * A tab is a pure presenter: the dialog owns the query and the page, and hands
 * this the rows and the footer. Server-paged, because 밀가루 alone is named by
 * 94,342 labels (measured 2026-09-09) and a client page would have to hold them all.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import DetailSection from '@/components/detail/DetailSection'
import ServerPagedTable from '@/components/detail/ServerPagedTable'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import Label from '@/components/label/Label'
import type { ServerTablePagination } from '@/hooks/useServerTablePage'
import type { FoodItemReport } from '@/types/food'

// One colour per registry, so the three kinds are told apart at a glance and a
// new kind is a line here rather than a ternary that silently lumps it in.
const KIND_COLOUR = {
  domestic: 'info',
  livestock: 'warning',
  import: 'success',
  health_functional: 'secondary',
} as const

export default function FoodRawMaterialItemReportsTab({
  rows,
  pagination,
  loading,
}: {
  rows: FoodItemReport[]
  pagination: ServerTablePagination
  /** The dialog's query is in flight - the table draws the bar and locks its footer. */
  loading: boolean
}) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  // 구분 carries a badge, and a badge does not shrink: the widest is the English
  // 'Health functional food' at 196px, 18% of the table.
  const columns: TableColumn[] = [
    { key: 'kind', label: t('item_report.table.kind'), width: '18%' },
    { key: 'number', label: t('item_report.table.number'), width: '20%' },
    { key: 'product', label: t('item_report.table.product'), width: '28%' },
    { key: 'type', label: t('item_report.table.type'), width: '17%' },
    { key: 'business', label: t('item_report.table.business'), width: '17%' },
  ]

  return (
    <DetailSection name="link" title={t('raw_material.tabs.products')}>
      <ServerPagedTable
        columns={columns}
        rows={rows}
        rowKey={(report) => report.id}
        pagination={pagination}
        empty={tCommon('messages.no_data')}
        loading={loading}
        renderCells={(report) => (
          <>
            <TableCell>
              <Label variant="soft" color={KIND_COLOUR[report.report_kind]}>
                {t(`item_report.kind.${report.report_kind}`)}
              </Label>
            </TableCell>
            <TableCell>
              <ClippedText text={report.item_report_no} />
            </TableCell>
            <TableCell>
              <ClippedText text={report.product_name ?? '—'} />
            </TableCell>
            <TableCell>
              <ClippedText text={report.product_type_name ?? '—'} />
            </TableCell>
            <TableCell>
              <ClippedText text={report.business_name ?? '—'} />
            </TableCell>
          </>
        )}
      />
    </DetailSection>
  )
}
