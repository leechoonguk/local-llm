/**
 * Batch list — the same list template as `UserList`, different columns.
 *
 * `description` is not a column: with the schedule's own fields (code, cron,
 * state) plus four row actions, the minimum widths exceeded the card and the
 * grid clipped the last action buttons — measured at a 1280px viewport. The
 * description is one click away in the edit dialog; a stop button that cannot
 * be reached is not.
 *
 * The similarity is the standard, not duplication to be factored away: a
 * generic `<CrudList domain={...}>` would hide the columns, the dialogs and the
 * empty sentence behind configuration, and every screen that needed one
 * exception would fork it. The shape is copied; the decisions stay local.
 */

import { useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Button, Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import BatchFormDialog from '@/sections/batch/BatchFormDialog'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListToolbar from '@/components/data-grid/ListToolbar'
import { rowActionsColumn } from '@/components/data-grid/RowActions'
import Label from '@/components/label/Label'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import { useBatchList, useDeleteBatch, useRunBatch } from '@/lib/api/hooks/useBatch'
import { useCrudDialog } from '@/hooks/useCrudDialog'
import { useDataGridState } from '@/hooks/useDataGridState'
import { usePagedRows } from '@/hooks/usePagedRows'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import { formatDateTime } from '@/utils/formatTime'
import type { Batch } from '@/types/batch'

const TIMESTAMP_COLUMN_WIDTH = 180

const CRON_COLUMN_WIDTH = 130

const STATE_COLUMN_WIDTH = 110

export default function BatchList() {
  const { t } = useTranslation('batch')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const query = useBatchList(grid.params)
  const { rows, rowCount, paginationMeta } = usePagedRows(
    query.data,
    grid.paginationModel.page,
    grid.paginationModel.pageSize,
  )
  const dialog = useCrudDialog<Batch>()
  const deleteMutation = useDeleteBatch()
  const runMutation = useRunBatch()

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

  const columns = useMemo<GridColDef<Batch>[]>(
    () => [
      { field: 'name', headerName: t('table.name'), flex: 1, minWidth: 140 },
      { field: 'code', headerName: t('table.code'), flex: 1, minWidth: 150 },
      {
        field: 'cron',
        headerName: t('table.cron'),
        width: CRON_COLUMN_WIDTH,
      },
      {
        field: 'enabled',
        headerName: t('table.enabled'),
        width: STATE_COLUMN_WIDTH,
        align: 'center',
        headerAlign: 'center',
        renderCell: ({ row }) => (
          <Label color={row.enabled ? 'success' : 'default'}>
            {row.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
          </Label>
        ),
      },
      {
        field: 'created_at',
        headerName: tCommon('fields.created_at'),
        width: TIMESTAMP_COLUMN_WIDTH,
        valueFormatter: (value: string) => formatDateTime(value),
      },
      rowActionsColumn<Batch>({
        count: 4,
        actions: ({ row }) => [
          {
            label: t('actions.run'),
            icon: 'run',
            onClick: () => void handleRun(row, true),
          },
          {
            label: t('actions.stop'),
            icon: 'stop',
            onClick: () => void handleRun(row, false),
          },
          {
            label: tCommon('actions.edit'),
            icon: 'edit',
            onClick: () => dialog.openEdit(row),
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
    [t, tCommon, dialog, handleRun],
  )

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
        <ListToolbar
          title={t('list_title')}
          count={rows.length}
          addLabel={tCommon('actions.add')}
          onAdd={dialog.openCreate}
          density={grid.density}
          onDensityChange={grid.setDensity}
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
          densityLabel={tCommon('actions.density')}
          refreshLabel={tCommon('actions.retry')}
        />

        {query.isError && (
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={() => void query.refetch()}>
                {tCommon('actions.retry')}
              </Button>
            }
          >
            {tCommon('messages.load_failed')}
          </Alert>
        )}

        <ServerDataGrid
          rows={rows}
          columns={columns}
          rowCount={rowCount}
          emptyTitle={tCommon('messages.no_data')}
          loading={query.isLoading}
          paginationModel={grid.paginationModel}
          onPaginationModelChange={grid.setPaginationModel}
          paginationMeta={paginationMeta}
          density={grid.density}
          columnVisibilityModel={grid.columnVisibilityModel}
          onColumnVisibilityModelChange={grid.setColumnVisibilityModel}
          localeText={grid.localeText}
        />
      </Card>

      <BatchFormDialog open={dialog.isCreateOpen} onClose={dialog.close} batch={null} />

      <BatchFormDialog open={dialog.isEditOpen} onClose={dialog.close} batch={dialog.selected} />

      <ConfirmDialog
        open={dialog.isDeleteOpen}
        title={t('delete_title')}
        content={
          <>
            {t('messages.delete_confirm', { name: dialog.selected?.name ?? '' })}
            <br />
            {tCommon('messages.cannot_undo')}
          </>
        }
        confirmLabel={tCommon('actions.delete')}
        cancelLabel={tCommon('actions.cancel')}
        pending={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
        onClose={dialog.close}
      />
    </>
  )
}
