/**
 * Batch list — the same list template as `UserList`, editing in place.
 *
 * A schedule's mutable values are `cron` and `enabled`, and both are columns:
 * the row is where they are changed, so there is no edit dialog asking again
 * for what the row already shows (rule://frontend-screens, Editing In Place).
 * `code` stays read-only beside them — the server refuses to repoint a schedule
 * at another job, so an editable code cell would accept a value the API
 * ignores. The dialog creates, because `code` is only ever chosen there.
 *
 * The row is the door to its run log: a schedule's question is almost always
 * "did it run", and that was two clicks behind an icon. The door is safe beside
 * the editors because `ServerDataGrid` guards it — a row in edit mode has no
 * door, and a click inside the actions cell belongs to its button. There is no
 * history button beside it: the intent had two controls, and the row is the one
 * a reader finds without looking for it, so the actions column carries four
 * verbs and gives the width back to the data.
 *
 * The similarity is the standard, not duplication to be factored away: a
 * generic `<CrudList domain={...}>` would hide the columns, the dialogs and the
 * empty sentence behind configuration, and every screen that needed one
 * exception would fork it. The shape is copied; the decisions stay local.
 */

import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Card, Switch } from '@mui/material'
import { useGridApiRef } from '@mui/x-data-grid'
import type { GridColDef } from '@mui/x-data-grid'
import BatchFormDialog, {
  CRON_FIELD_PATTERN,
  CRON_MAX_LENGTH,
} from '@/sections/batch/BatchFormDialog'
import BatchRunsDialog from '@/sections/batch/BatchRunsDialog'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import { rowActionsColumn } from '@/components/data-grid/RowActions'
import Label from '@/components/label/Label'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import {
  useBatch,
  useBatchList,
  useDeleteBatch,
  useRunBatch,
  useUpdateBatch,
} from '@/lib/api/hooks/useBatch'
import { useCrudDialog } from '@/hooks/useCrudDialog'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useRowEditor } from '@/hooks/useRowEditor'
import type { RowRefusal } from '@/hooks/useRowEditor'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import { TIMESTAMP_COLUMN_FLOOR } from '@/config'
import { formatDateTime } from '@/utils/formatTime'
import type { Batch, BatchListParams } from '@/types/batch'

/**
 * Every column has a **floor** and a **share** (rule://frontend-screens, Column
 * Width). Measured at the body size (2026-09-09): the widest code
 * (`purge_expired_refresh_tokens`) is 167px of ink, so a code - a row's
 * identity - never clips; the widest name is 189px but a name is prose the
 * grid's tooltip completes, so its floor is lower and its share the largest;
 * a cron is 53px, a badge one word.
 *
 * Six floors totalling **915** (210·108·107·135·185 and the actions column's
 * 174) against the 1,080px the card leaves beside the nav, which is the budget
 * `checkGridsFitTheirCard` holds this screen to: the actions are last, so
 * anything over the card takes the buttons with it. It used to be 1,132 with a
 * `name` column at 217px, and the name was the code restyled on all 33 rows -
 * dropping it is what bought the fit. `cron` floors at its own ink (68px of
 * `30 20 * * 0` plus the cell's 40px of gutter): at 104 the grid ellipsised a
 * five-field expression into `30 20 * ...`, which is not a cron anyone can read.
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  code: { floor: 210, share: 1.5 },
  cron: { floor: 108, share: 0.4 },
  enabled: { floor: 107, share: 0.4 },
  running: { floor: 135, share: 0.4 },
  created_at: { floor: TIMESTAMP_COLUMN_FLOOR, share: 0.8 },
}

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

/**
 * The columns this screen filters, in the order the boxes stand.
 *
 * The list is the query parameters' names, so a box, its label and the
 * parameter it sends cannot drift apart: a name the router does not read fails
 * `check-frontend-types` rather than filtering nothing quietly.
 */
const FILTER_FIELDS = ['code'] as const

const FILTER_LABEL_KEYS = {
  code: 'filter.code',
} as const

/** The query parameter that opens one schedule's run log. */
const RUNS_PARAM = 'runs'

/** The columns a row edits, and what each can be wrong about. */
const EDITABLE_FIELDS = ['cron'] as const

type FilterField = (typeof FILTER_FIELDS)[number]

type EditableField = (typeof EDITABLE_FIELDS)[number]

interface FieldProblem {
  key:
    | 'validation.cron_required'
    | 'validation.cron_max'
    | 'validation.cron_invalid'
  count?: number
}

export default function BatchList() {
  const { t } = useTranslation('batch')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const apiRef = useGridApiRef()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<BatchListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useBatchList(params)
  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0
  const dialog = useCrudDialog<Batch>()
  /**
   * The run log is addressed by the URL, not by a row object in state.
   *
   * The header's failure bell links straight to one schedule's log
   * (`/batch?runs=<id>`), and a dialog opened from component state cannot be
   * reached that way. One source, so a link and a row click land on the same
   * dialog — and the record comes from its own read, because the schedule the
   * link names may sit on a page this grid is not showing.
   */
  const [searchParams, setSearchParams] = useSearchParams()
  const historyBatchId = searchParams.get(RUNS_PARAM)
  const historyQuery = useBatch(historyBatchId)
  const historyBatch = historyQuery.data ?? null
  const openHistory = useCallback(
    (batchId: string) => setSearchParams({ [RUNS_PARAM]: batchId }),
    [setSearchParams],
  )
  const closeHistory = useCallback(() => setSearchParams({}), [setSearchParams])
  const deleteMutation = useDeleteBatch()
  const runMutation = useRunBatch()
  const updateMutation = useUpdateBatch()

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  const handleRun = useCallback(
    async (batch: Batch, running: boolean) => {
      try {
        await runMutation.mutateAsync({ id: batch.id, data: { running } })
        toast.success(running ? t('messages.run_started') : t('messages.run_stopped'))
      } catch (error) {
        toast.error(serverErrorMessage(toApiError(error).code, tCommon))
      }
    },
    [runMutation, toast, t, tCommon],
  )

  /**
   * Why a row cannot be saved, in the words the reader gets — or `null`.
   *
   * The screen owns this and `problemOf`; `useRowEditor` owns what is done with
   * the answer, which is the same on every screen that edits in place.
   */
  const refusal = useCallback(
    (row: Batch): RowRefusal<EditableField> | null => {
      for (const field of EDITABLE_FIELDS) {
        const problem = problemOf(field, String(row[field] ?? ''))
        if (problem === null) continue
        return { field, sentence: t(problem.key, { count: problem.count ?? 0 }) }
      }
      return null
    },
    [t],
  )
  const editor = useRowEditor<Batch, EditableField>({ apiRef, refusal })

  const columns = useMemo<GridColDef<Batch>[]>(
    () => [
      { ...sized('code'), headerName: t('table.code') },
      {
        ...sized('cron'),
        headerName: t('table.cron'),
        editable: true,
        // The same rule the blocked save states in words, so a red cell and the
        // sentence can never disagree.
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: problemOf('cron', String(params.props.value ?? '')) !== null,
        }),
      },
      {
        ...sized('enabled'),
        headerName: t('table.enabled'),
        align: 'center',
        headerAlign: 'center',
        type: 'boolean',
        editable: true,
        renderCell: ({ row }) => (
          <Label color={row.enabled ? 'success' : 'default'}>
            {row.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
          </Label>
        ),
        /**
         * `type: 'boolean'` edits through a bare checkbox, the one control that
         * appears nowhere else in the app: the read cell is a chip and the
         * create dialog uses a `Switch` for the same field. A switch also reads
         * as the state it is in, where a checkbox reads as a choice being ticked.
         */
        renderEditCell: ({ id, value, field, api }) => (
          <Switch
            size="small"
            checked={value === true}
            onChange={(event) =>
              void api.setEditCellValue({ id, field, value: event.target.checked })
            }
          />
        ),
      },
      {
        /**
         * Two different facts, so two columns: `enabled` is whether the clock
         * will start this job, `running` is whether it is executing right now.
         * One badge for both would have to say "사용 · 실행 중" or drop one of
         * them, and the run and stop buttons answer to *this* one.
         */
        ...sized('running'),
        headerName: t('table.running'),
        align: 'center',
        headerAlign: 'center',
        sortable: false,
        renderCell: ({ row }) => (
          <Label color={row.running ? 'info' : 'default'}>
            {row.running ? t('status.running') : t('status.idle')}
          </Label>
        ),
      },
      {
        ...sized('created_at'),
        headerName: tCommon('fields.created_at'),
        valueFormatter: (value: string) => formatDateTime(value),
      },
      rowActionsColumn<Batch>({
        count: 4,
        actions: ({ id, row }) =>
          editor.isEditing(id)
            ? [
                {
                  label: tCommon('actions.save'),
                  icon: 'check',
                  tone: 'primary',
                  onClick: () => editor.commitEdit(id),
                },
                {
                  label: tCommon('actions.cancel'),
                  icon: 'close',
                  onClick: () => editor.cancelEdit(id),
                },
              ]
            : [
                {
                  label: t('actions.run'),
                  icon: 'run',
                  // The verbs follow the state the row reports: starting a job that is
                  // already running answers 409, and stopping one that is not is a
                  // request that cancels nothing.
                  disabled: row.running,
                  onClick: () => void handleRun(row, true),
                },
                {
                  label: t('actions.stop'),
                  icon: 'stop',
                  disabled: !row.running,
                  onClick: () => void handleRun(row, false),
                },
                {
                  label: tCommon('actions.edit'),
                  icon: 'edit',
                  onClick: () => editor.startEdit(id),
                },
                {
                  label: tCommon('actions.delete'),
                  icon: 'delete',
                  tone: 'error',
                  onClick: () => dialog.openDelete(row),
                },
              ],
      }),
    ],
    [t, tCommon, dialog, handleRun, editor],
  )

  /**
   * One PATCH for the whole row, because that is the endpoint: `PATCH /batch/{id}`
   * takes the resource, not a field. Returning the server's row is what puts the
   * new `version` in the grid; the guard around it is what keeps a refused row
   * open with one sentence.
   */
  const handleRowUpdate = editor.guardRowUpdate(async (updated: Batch, original: Batch) => {
    const unchanged = updated.cron === original.cron && updated.enabled === original.enabled
    if (unchanged) return original

    const saved = await updateMutation.mutateAsync({
      id: updated.id,
      data: {
        cron: updated.cron,
        enabled: updated.enabled,
      },
    })
    toast.success(tCommon('messages.saved'))
    return saved
  })

  const handleDelete = async () => {
    if (dialog.selected === null) return
    try {
      await deleteMutation.mutateAsync(dialog.selected.id)
      toast.success(tCommon('messages.deleted'))
      dialog.close()
    } catch (error) {
      toast.error(serverErrorMessage(toApiError(error).code, tCommon))
    }
  }

  return (
    <>
      <Card>
        <ListCardHead
          title={t('list_title')}
          count={rowCount}
          reset={{
            label: tCommon('actions.reset'),
            onReset: filters.reset,
            disabled: !filters.isFiltered,
          }}
          add={{ label: tCommon('actions.add'), onAdd: dialog.openCreate }}
          refreshLabel={tCommon('actions.retry')}
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
          filters={
            <ListFilters
              fields={FILTER_FIELDS.map((field) => ({ name: field, label: t(FILTER_LABEL_KEYS[field]) }))}
              values={filters.inputs}
              onChange={(name, value) => filters.setInput(name as FilterField, value)}
            />
          }
        />

        <ServerDataGrid
          rows={rows}
          columns={columns}
          rowCount={rowCount}
          emptyTitle={tCommon('messages.no_data')}
          loading={query.isFetching}
          paginationModel={grid.paginationModel}
          onPaginationModelChange={grid.setPaginationModel}
        sortModel={grid.sortModel}
        onSortModelChange={grid.setSortModel}
          density={grid.density}
          columnVisibilityModel={grid.columnVisibilityModel}
          onColumnVisibilityModelChange={grid.setColumnVisibilityModel}
          localeText={grid.localeText}
          onRowClick={(row) => openHistory(row.id)}
          rowModesModel={editor.rowModes}
          onRowModesModelChange={editor.setRowModes}
          processRowUpdate={handleRowUpdate}
          apiRef={apiRef}
          onProcessRowUpdateError={(error) =>
            editor.rowUpdateError(error, (failure) => serverErrorMessage(toApiError(failure).code, tCommon))
          }
        />
      </Card>

      <BatchRunsDialog open={historyBatch !== null} batch={historyBatch} onClose={closeHistory} />

      <BatchFormDialog open={dialog.isCreateOpen} onClose={dialog.close} />

      <ConfirmDialog
        open={dialog.isDeleteOpen}
        title={t('delete_title')}
        content={t('messages.delete_confirm', { code: dialog.selected?.code ?? '' })}
        confirmLabel={tCommon('actions.delete')}
        cancelLabel={tCommon('actions.cancel')}
        pending={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
        onClose={dialog.close}
      />
    </>
  )
}

/**
 * The one place a schedule's editable value is judged.
 *
 * The red cell and the sentence a blocked save shows come from this function, so
 * a cell can never be red for a reason the message does not name, or refuse a
 * save the message calls fine. `cron` is the only free text a row edits - the
 * code is identity and `enabled` is a switch - so the rule and its wording sit
 * together here.
 */
function problemOf(field: EditableField, value: string): FieldProblem | null {
  const trimmed = value.trim()
  if (field !== 'cron') return null
  if (trimmed === '') return { key: 'validation.cron_required' }
  if (trimmed.length > CRON_MAX_LENGTH) return { key: 'validation.cron_max', count: CRON_MAX_LENGTH }
  return CRON_FIELD_PATTERN.test(trimmed) ? null : { key: 'validation.cron_invalid' }
}
