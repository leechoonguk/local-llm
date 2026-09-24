/**
 * The provider's call log — what left this process, and what came back.
 *
 * The third leg of the operations pattern (rule://product-areas): the rows are
 * written on every exchange, by whatever exercised the operation, and before
 * this tab existed nothing read them. A provider you can configure and exercise
 * but whose traffic you cannot see is a provider you cannot diagnose.
 *
 * `ServerPagedTable` over `useServerTablePage`, like a schedule's runs: the log
 * grows by a row per call forever, so it cannot be fetched whole and sliced.
 * Bodies and headers are not columns — they are stored for an incident, and the
 * page would otherwise carry a provider document per row
 * (`IntegrationCallReadResponse`).
 */

import { TableCell } from '@mui/material'
import type { ComponentProps } from 'react'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import DetailSection from '@/components/detail/DetailSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import ServerPagedTable from '@/components/detail/ServerPagedTable'
import Label from '@/components/label/Label'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useServerTablePage } from '@/hooks/useServerTablePage'
import { useIntegrationCallList } from '@/lib/api/hooks/useIntegration'
import { formatDateTime } from '@/utils/formatTime'
import type { CallOutcome, IntegrationCall } from '@/types/integration'

type LabelColor = NonNullable<ComponentProps<typeof Label>['color']>

/**
 * The log's whole vocabulary — `ck_integration_call_outcome`, verbatim.
 *
 * Keyed by `CallOutcome`, so the constraint gaining a sixth ending fails the
 * build here instead of drawing a grey badge nobody reads.
 */
const OUTCOME_COLORS: Record<CallOutcome, LabelColor> = {
  SUCCESS: 'success',
  REFUSED: 'error',
  TIMEOUT: 'warning',
  UNREACHABLE: 'error',
  RATE_LIMITED: 'warning',
}

/** Percentages, so this table reads at the dialog's other tables' rhythm. */
const WIDTHS = ['14%', '16%', '30%', '10%', '10%', '20%'] as const

export default function IntegrationCallsTab({ integrationId }: { integrationId: string | null }) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')

  const page = useServerTablePage<IntegrationCall>()
  const query = useIntegrationCallList(integrationId, page.params)
  const calls = page.resolve(query.data)

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  const columns: TableColumn[] = [
    { key: 'outcome', width: WIDTHS[0], label: t('calls.table.outcome') },
    { key: 'operation', width: WIDTHS[1], label: t('calls.table.operation') },
    { key: 'url', width: WIDTHS[2], label: t('calls.table.url') },
    { key: 'status', width: WIDTHS[3], label: t('calls.table.status'), align: 'right' },
    { key: 'duration', width: WIDTHS[4], label: t('calls.table.duration'), align: 'right' },
    { key: 'called_at', width: WIDTHS[5], label: t('calls.table.called_at') },
  ]

  return (
    <DetailSection name="view" title={t('tabs.calls')}>
      <ServerPagedTable
        columns={columns}
        rows={calls.rows}
        rowKey={(call) => call.id}
        pagination={calls.pagination}
        empty={t('calls.empty')}
        loading={query.isFetching}
        renderCells={(call) => (
          <>
            <TableCell>
              <Label color={OUTCOME_COLORS[call.outcome]}>
                {t(`calls.outcome.${call.outcome}`)}
              </Label>
            </TableCell>
            <TableCell>
              <ClippedText text={call.operation_code} />
            </TableCell>
            {/* The URL is the key during an incident: these providers carry the
                credential as a path segment, so the client scrubbed it before the
                row was written and what is shown is what was sent, minus secrets. */}
            <TableCell>
              <ClippedText text={`${call.method} ${call.url}`} />
            </TableCell>
            <TableCell align="right">
              <ClippedText text={call.status_code === null ? '—' : String(call.status_code)} />
            </TableCell>
            <TableCell align="right">
              <ClippedText text={`${(call.duration_ms / 1000).toFixed(1)}s`} />
            </TableCell>
            <TableCell>
              <ClippedText
                text={
                  call.error_code === null
                    ? formatDateTime(call.created_at)
                    : `${formatDateTime(call.created_at)} · ${call.error_code}`
                }
              />
            </TableCell>
          </>
        )}
      />
    </DetailSection>
  )
}
