/**
 * Batch run history — one schedule's executions, and the windows of one run.
 *
 * Both tables are `ServerPagedTable` over `useServerTablePage`: the run log
 * grows by one row per night forever and a long resumable sync writes a step
 * per page, so neither collection can be fetched whole and sliced. The page is
 * a request here, which is also why the two footers can disagree — the reader
 * pages the runs without losing the steps of the run they opened.
 *
 * Selecting a run **toggles**: the row that is open closes on a second click,
 * and the chevron the frame draws says which state the row is in before it is
 * clicked. Choosing a different run resets the steps to page one — the second
 * page of the previous run's windows is not a page of these.
 *
 * Not `ServerDataGrid`: that template owns a page's worth of chrome — density,
 * column visibility, a toolbar — and its state is the screen's. Two of them
 * nested in a dialog that closes would carry all of it for a log nobody sorts.
 *
 * The status vocabulary is the backend's CHECK constraint verbatim; rendering
 * it through `Label` (never `Chip`) is the design system's badge rule.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogTitle, TableCell, Typography } from '@mui/material'
import type { ComponentProps } from 'react'
import ClippedText from '@/components/detail/ClippedText'
import { RECORD_SURFACE } from '@/config'
import Label from '@/components/label/Label'
import ServerPagedTable from '@/components/detail/ServerPagedTable'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useServerTablePage } from '@/hooks/useServerTablePage'
import { useBatchRunList, useBatchRunStepList } from '@/lib/api/hooks/useBatch'
import { formatDateTime } from '@/utils/formatTime'
import type { Batch, BatchRun, BatchRunStatus, BatchStep } from '@/types/batch'

type LabelColor = NonNullable<ComponentProps<typeof Label>['color']>

/**
 * The run table's whole vocabulary — the backend's CHECK constraint, verbatim.
 *
 * Keyed by `BatchRunStatus`, so the compiler refuses a map that misses an
 * ending: the constraint gaining a sixth value fails the build here rather than
 * rendering as a grey badge nobody reads. A step's two endings are a subset, so
 * the same map serves both tables.
 */
const STATUS_COLORS: Record<BatchRunStatus, LabelColor> = {
  RUNNING: 'info',
  SUCCEEDED: 'success',
  FAILED: 'error',
  STOPPED: 'warning',
  INTERRUPTED: 'default',
  SKIPPED: 'default',
}

/**
 * Widths are percentages, so the two tables of one dialog read at the same
 * rhythm; the labels are built at the call site with **literal** keys. Composed
 * ones (`t(`runs.steps_table.${column.key}`)`) type-check and pass every gate
 * while the header renders the key itself — measured on this screen: three step
 * columns read `runs.steps_table.duration`. `check-frontend-i18n` can only see
 * a key it can read.
 */
const RUN_WIDTHS = ['14%', '26%', '22%', '11%', '11%', '11%'] as const

const STEP_WIDTHS = ['8%', '20%', '12%', '12%', '12%', '16%', '20%'] as const

interface BatchRunsDialogProps {
  open: boolean
  batch: Batch | null
  onClose: () => void
}

export default function BatchRunsDialog({ open, batch, onClose }: BatchRunsDialogProps) {
  const { t } = useTranslation('batch')
  const { t: tCommon } = useTranslation('common')
  const [selectedRun, setSelectedRun] = useState<BatchRun | null>(null)

  const runsPage = useServerTablePage<BatchRun>()
  const stepsPage = useServerTablePage<BatchStep>()

  const batchId = open && batch !== null ? batch.id : null
  const runsQuery = useBatchRunList(batchId, runsPage.params)
  const stepsQuery = useBatchRunStepList(batchId, selectedRun?.id ?? null, stepsPage.params)

  const runs = runsPage.resolve(runsQuery.data)
  const steps = stepsPage.resolve(stepsQuery.data)

  useQueryErrorToast(runsQuery, tCommon('messages.load_failed'))
  useQueryErrorToast(stepsQuery, tCommon('messages.load_failed'))

  const handleSelect = (run: BatchRun) => {
    setSelectedRun((current) => (current?.id === run.id ? null : run))
    stepsPage.reset()
  }

  const handleClose = () => {
    setSelectedRun(null)
    runsPage.reset()
    stepsPage.reset()
    onClose()
  }

  const runColumns: TableColumn[] = [
    { key: 'status', width: RUN_WIDTHS[0], label: t('runs.table.status') },
    { key: 'trigger', width: RUN_WIDTHS[1], label: t('runs.table.trigger') },
    { key: 'started_at', width: RUN_WIDTHS[2], label: t('runs.table.started_at') },
    { key: 'duration', width: RUN_WIDTHS[3], label: t('runs.table.duration'), align: 'right' },
    { key: 'result', width: RUN_WIDTHS[4], label: t('runs.table.result'), align: 'right' },
    { key: 'error', width: RUN_WIDTHS[5], label: t('runs.table.error') },
  ]

  /**
   * `sequence` is left-aligned: it is the page's ordinal, not a measured amount.
   * Right alignment is for the quantities a reader compares down the column —
   * received, written, duration — and a label sitting there read as one of them.
   */
  const stepColumns: TableColumn[] = [
    { key: 'sequence', width: STEP_WIDTHS[0], label: t('runs.steps_table.sequence') },
    { key: 'window', width: STEP_WIDTHS[1], label: t('runs.steps_table.window') },
    { key: 'received', width: STEP_WIDTHS[2], label: t('runs.steps_table.received'), align: 'right' },
    { key: 'written', width: STEP_WIDTHS[3], label: t('runs.steps_table.written'), align: 'right' },
    { key: 'duration', width: STEP_WIDTHS[4], label: t('runs.table.duration'), align: 'right' },
    { key: 'status', width: STEP_WIDTHS[5], label: t('runs.table.status') },
    { key: 'error', width: STEP_WIDTHS[6], label: t('runs.table.error') },
  ]

  return (
    <Dialog open={open} onClose={handleClose} maxWidth={RECORD_SURFACE.DIALOG_MAX_WIDTH} fullWidth>
      <DialogTitle>{t('runs.title', { code: batch?.code ?? '' })}</DialogTitle>
      <DialogContent>
        <ServerPagedTable
          columns={runColumns}
          rows={runs.rows}
          rowKey={(run) => run.id}
          pagination={runs.pagination}
          empty={t('runs.empty')}
          loading={runsQuery.isFetching}
          expanded={(run) => selectedRun?.id === run.id}
          onRowClick={handleSelect}
          renderCells={(run) => (
            <>
              <TableCell>
                <Label color={STATUS_COLORS[run.status]}>
                  {t(`runs.status.${run.status}`)}
                </Label>
              </TableCell>
              <TableCell>
                <ClippedText
                  text={`${t(`runs.trigger.${run.trigger}`)} · ${run.triggered_by}${
                    run.stopped_by !== null ? ` → ${run.stopped_by}` : ''
                  }`}
                />
              </TableCell>
              <TableCell>
                <ClippedText text={formatDateTime(run.started_at)} />
              </TableCell>
              <TableCell align="right">
                <ClippedText
                  text={run.duration_ms !== null ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}
                />
              </TableCell>
              <TableCell align="right">
                <ClippedText text={String(run.result ?? '—')} />
              </TableCell>
              <TableCell>
                <ClippedText text={run.error_code ?? '—'} />
              </TableCell>
            </>
          )}
        />

        {selectedRun !== null && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              {t('runs.steps_title')}
            </Typography>

            <ServerPagedTable
              columns={stepColumns}
              rows={steps.rows}
              rowKey={(step) => step.id}
              pagination={steps.pagination}
              empty={t('runs.steps_empty')}
              loading={stepsQuery.isFetching}
              renderCells={(step) => (
                <>
                  <TableCell>
                    <ClippedText text={String(step.sequence)} />
                  </TableCell>
                  <TableCell>
                    <ClippedText
                      text={
                        step.range_start !== null && step.range_end !== null
                          ? `${step.range_start}–${step.range_end}`
                          : '—'
                      }
                    />
                  </TableCell>
                  <TableCell align="right">
                    <ClippedText text={String(step.received ?? '—')} />
                  </TableCell>
                  <TableCell align="right">
                    <ClippedText text={String(step.written ?? '—')} />
                  </TableCell>
                  <TableCell align="right">
                    <ClippedText text={`${(step.duration_ms / 1000).toFixed(1)}s`} />
                  </TableCell>
                  <TableCell>
                    <Label color={STATUS_COLORS[step.status]}>
                      {t(`runs.status.${step.status}`)}
                    </Label>
                  </TableCell>
                  <TableCell>
                    <ClippedText text={step.error_code ?? '—'} />
                  </TableCell>
                </>
              )}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
