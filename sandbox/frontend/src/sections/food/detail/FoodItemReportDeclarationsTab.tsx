/**
 * What the product declared - and the registry decides which question that is.
 *
 * A 수입식품 declares a **수입신고**: one crossing of one lot, 3.6 times per
 * product on average and 1,223 times at the widest. Every other registry
 * declares a **생산실적**: one year's figure against the capacity behind it.
 * The two never meet - measured 2026-09-20, no product carries both shapes -
 * so this draws one of two tables rather than one table with half its cells
 * empty, which is what it did before: seven columns of which three or four
 * were always `—`.
 *
 * **An action attaches to a crossing, never to a figure.** The portal hangs a
 * recall on one 수입신고 of a product's many, so the import table carries a
 * 조치 column and the row that was acted on says so. A 생산실적 is a year's
 * total; nothing an authority did lands on a number, and a column that tried
 * would be pairing two facts that share only a year. So the column exists on
 * one table and not on the other, because the axis exists on one and not the
 * other. What was inspected is read whole in 검사·조치 이력, where each row
 * names the lot it acted on.
 *
 * 수입량 is absent for the same kind of reason: 생산실적 is a figure the maker
 * files per item, and imports have no such filing - the portal publishes import
 * weight as national trade statistics, by country and 품목, never per product.
 * The quantity a reader can have here is how many times it crossed.
 *
 * A tab is a pure presenter: the dialog owns the query and the page and hands
 * this the rows and the footer.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import DetailSection from '@/components/detail/DetailSection'
import Label from '@/components/label/Label'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import ServerPagedTable from '@/components/detail/ServerPagedTable'
import type { ServerTablePagination } from '@/hooks/useServerTablePage'
import type { FoodItemReportDeclaration, ReportKind } from '@/types/food'
import { formatPortalDate } from '@/utils/formatTime'

/** The registry whose declarations are crossings; every other one files figures. */
const IMPORT_KIND: ReportKind = 'import'

export default function FoodItemReportDeclarationsTab({
  reportKind,
  rows,
  pagination,
  loading,
}: {
  /** Which registry the product is in - it chooses the table, not just the wording. */
  reportKind: ReportKind
  rows: FoodItemReportDeclaration[]
  pagination: ServerTablePagination
  /** The dialog's query is in flight - the table draws the bar and locks its footer. */
  loading: boolean
}) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')
  const isImport = reportKind === IMPORT_KIND

  const columns: TableColumn[] = isImport
    ? [
        { key: 'date', label: t('item_report.declaration.processed_date'), width: '14%' },
        { key: 'kind', label: t('item_report.declaration.kind'), width: '16%' },
        { key: 'export', label: t('item_report.declaration.export_country'), width: '14%' },
        { key: 'expiry', label: t('item_report.declaration.expiry'), width: '22%' },
        { key: 'records', label: t('item_report.declaration.records'), width: '17%' },
        { key: 'key', label: t('item_report.declaration.key'), width: '17%' },
      ]
    : [
        // No key column: 신고키 numbers a 신고, and a 생산실적 is a year's
        // figure, not one. The row is identified by its year.
        { key: 'year', label: t('item_report.declaration.report_year'), width: '25%' },
        { key: 'production', label: t('item_report.declaration.production_qty'), width: '35%' },
        { key: 'capacity', label: t('item_report.declaration.annual_capacity'), width: '40%' },
      ]

  return (
    <DetailSection
      name="link"
      title={t(isImport ? 'item_report.declaration.section' : 'item_report.production.section')}
    >
      <ServerPagedTable
        columns={columns}
        rows={rows}
        rowKey={(declaration) => declaration.id}
        pagination={pagination}
        empty={tCommon('messages.no_data')}
        loading={loading}
        renderCells={(declaration) =>
          isImport ? (
            <>
              <TableCell>
                <ClippedText text={formatPortalDate(declaration.processed_date)} />
              </TableCell>
              <TableCell>
                {declaration.declaration_kind === null ? (
                  <ClippedText text="—" />
                ) : (
                  <Label variant="soft" color="info">
                    {declaration.declaration_kind}
                  </Label>
                )}
              </TableCell>
              <TableCell>
                <ClippedText text={declaration.export_country ?? '—'} />
              </TableCell>
              <TableCell>
                <ClippedText
                  text={
                    declaration.expiry_from === null && declaration.expiry_to === null
                      ? '—'
                      : `${declaration.expiry_from ?? '—'} ~ ${declaration.expiry_to ?? '—'}`
                  }
                />
              </TableCell>
              <TableCell>
                {declaration.recall_grade !== null ? (
                  <Label variant="soft" color="error">
                    {t('item_report.declaration.recalled', { grade: declaration.recall_grade })}
                  </Label>
                ) : declaration.failed_record_count > 0 ? (
                  <Label variant="soft" color="warning">
                    {t('item_report.declaration.failed', {
                      count: declaration.failed_record_count,
                    })}
                  </Label>
                ) : declaration.record_count > 0 ? (
                  // A recall the portal published without a grade - 63 of 377.
                  // It still happened, so the row says so rather than reading
                  // as untouched.
                  <Label variant="soft" color="warning">
                    {t('item_report.declaration.clean', { count: declaration.record_count })}
                  </Label>
                ) : (
                  <ClippedText text="—" />
                )}
              </TableCell>
              <TableCell>
                <ClippedText text={declaration.declaration_key} />
              </TableCell>
            </>
          ) : (
            <>
              <TableCell>
                <ClippedText text={declaration.report_year ?? '—'} />
              </TableCell>
              <TableCell>
                <ClippedText text={quantity(declaration.production_qty_kg)} />
              </TableCell>
              <TableCell>
                <ClippedText text={quantity(declaration.annual_capacity_kg)} />
              </TableCell>
            </>
          )
        }
      />
    </DetailSection>
  )
}

// ============================================================
// Functions
// ============================================================

/** A published quantity, grouped for reading; a figure the feed left out is absent. */
function quantity(value: string | null): string {
  if (value === null) return '—'
  const asNumber = Number(value)
  return Number.isNaN(asNumber) ? value : asNumber.toLocaleString()
}
