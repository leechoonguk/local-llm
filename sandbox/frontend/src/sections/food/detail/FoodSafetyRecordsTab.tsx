/**
 * 검사·조치 이력: every inspection of this product and what it was judged, and
 * every action taken about it - newest first.
 *
 * A section of the product's own screen, not a tab of its own. It is drawn only
 * where there is something to draw: 84,129 of 1.9 M products carry a record.
 * Every record of the product is read here, a window at a time - the table is
 * server-paged, so there is nowhere else to send a reader for "the rest".
 *
 * **The header counts before the reader reads.** A list of twelve rows does not
 * say "one of these was 부적합", and that is the question: the summary line
 * states the total, the failures and the day of the last one, and each number
 * is counted off these rows rather than stored anywhere.
 *
 * A pure presenter: the dialog owns the query and the page and hands this the
 * rows and the footer.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import DetailSection from '@/components/detail/DetailSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import ServerPagedTable from '@/components/detail/ServerPagedTable'
import Label from '@/components/label/Label'
import type { ServerTablePagination } from '@/hooks/useServerTablePage'
import type { JudgmentCode, RecordKind, FoodSafetyRecord } from '@/types/food'
import { formatPortalDate } from '@/utils/formatTime'

// One colour per kind of event, so a third feed is a line here rather than a
// ternary that draws it as one of the two that exist today.
const RECORD_COLOUR: Record<RecordKind, 'error' | 'warning' | 'info'> = {
  recall: 'error',
  inspection_failure: 'warning',
  collection_inspection: 'info',
}

// A failure is why a reader opens this; a pass is the answer most rows give.
const JUDGMENT_COLOUR: Record<JudgmentCode, 'error' | 'success' | 'default'> = {
  failed: 'error',
  passed: 'success',
  pending: 'default',
}

const RECORD_LABEL_KEYS = {
  recall: 'item_report.event.kind.recall',
  inspection_failure: 'item_report.event.kind.inspection_failure',
  collection_inspection: 'item_report.event.kind.collection_inspection',
} as const

/** What the event says, in the words of whichever feed said it.
 *
 * 수거검사 names no 검사항목 and no measurement - what it publishes is the plan
 * the specimen was collected under - so it reads its reason like a recall does.
 */
const summary = (event: FoodSafetyRecord) =>
  event.record_kind === 'inspection_failure'
    ? [event.test_item_name, event.test_result_text].filter(Boolean).join(' · ') || '—'
    : (event.reason ?? '—')

export default function FoodSafetyRecordsTab({
  rows,
  pagination,
  loading,
  failedCount,
  lastRecordedOn,
}: {
  rows: FoodSafetyRecord[]
  pagination: ServerTablePagination
  /** The dialog's query is in flight - the table draws the bar and locks its footer. */
  loading: boolean
  /**
   * How many of the product's records are failures, or null when none are.
   *
   * Counted over every record of the product, not over the page in hand: read
   * off one window, "0 failed" would be what page 2 says about a product whose
   * failure is on page 1. Null rather than 0, because "부적합 0건" is a line
   * that says nothing on a product that was only ever found fit.
   */
  failedCount: number | null
  lastRecordedOn: string | null
}) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  const columns: TableColumn[] = [
    { key: 'date', label: t('item_report.event.date'), width: '12%' },
    { key: 'kind', label: t('item_report.event.kind_label'), width: '13%' },
    { key: 'judgment', label: t('item_report.event.judgment'), width: '11%' },
    { key: 'summary', label: t('item_report.event.summary'), width: '24%' },
    { key: 'standard', label: t('item_report.event.standard'), width: '14%' },
    { key: 'grade', label: t('item_report.event.grade'), width: '16%' },
    // The lot the authority named - on an import, the 수입신고 the event sits
    // on, which the declarations tab marks with the same day.
    { key: 'lot', label: t('item_report.event.lot'), width: '10%' },
  ]

  return (
    <DetailSection
      name="shield"
      title={t('item_report.event.section')}
      subtitle={
        t('item_report.event.summary_line', {
          total: String(pagination.count),
          latest: lastRecordedOn === null ? '—' : formatPortalDate(lastRecordedOn),
        }) +
        (failedCount === null
          ? ''
          : ' · ' + t('item_report.event.summary_failed', { failed: String(failedCount) }))
      }
    >
      <ServerPagedTable
        columns={columns}
        rows={rows}
        rowKey={(event) => event.id}
        pagination={pagination}
        empty={tCommon('messages.no_data')}
        loading={loading}
        renderCells={(event) => (
          <>
            <TableCell>
              <ClippedText text={formatPortalDate(event.recorded_on)} />
            </TableCell>
            <TableCell>
              <Label variant="soft" color={RECORD_COLOUR[event.record_kind]}>
                {t(RECORD_LABEL_KEYS[event.record_kind])}
              </Label>
            </TableCell>
            <TableCell>
              {event.judgment_code === null ? (
                '—'
              ) : (
                <Label variant="soft" color={JUDGMENT_COLOUR[event.judgment_code]}>
                  {t(`item_report.event.judgments.${event.judgment_code}`)}
                </Label>
              )}
            </TableCell>
            <TableCell>
              <ClippedText text={summary(event)} />
            </TableCell>
            <TableCell>
              <ClippedText text={event.standard_text ?? '—'} />
            </TableCell>
            <TableCell>
              <ClippedText text={event.grade ?? event.institution_name ?? '—'} />
            </TableCell>
            <TableCell>
              <ClippedText text={formatPortalDate(event.lot_date)} />
            </TableCell>
          </>
        )}
      />
    </DetailSection>
  )
}
