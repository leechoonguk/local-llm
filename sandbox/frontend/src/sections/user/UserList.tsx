/**
 * The list screen template — every collection screen in the app is this shape.
 *
 * Four hooks in a fixed order, and nothing else decides state:
 *   `useDataGridState` → paging, density, column visibility
 *   `use<Domain>List`  → the page, cached and invalidated by the hooks layer
 *   `useCrudDialog`    → which dialog is open and on which row
 *   `useToast`         → the outcome of a mutation
 *
 * The screen owns presentation: columns, the empty sentence, and which dialogs
 * exist. It never builds a query key, a URL or an axios call.
 */

import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Button, Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListToolbar from '@/components/data-grid/ListToolbar'
import { rowActionsColumn } from '@/components/data-grid/RowActions'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import UserFormDialog from '@/sections/user/UserFormDialog'
import { useCrudDialog } from '@/hooks/useCrudDialog'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import { useDeleteUser, useUserList } from '@/lib/api/hooks/useUser'
import { formatDateTime } from '@/utils/formatTime'
import type { User } from '@/types/user'

const TIMESTAMP_COLUMN_WIDTH = 180

export default function UserList() {
  const { t } = useTranslation('user')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const query = useUserList(grid.params)
  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0
  const dialog = useCrudDialog<User>()
  const deleteMutation = useDeleteUser()

  const columns = useMemo<GridColDef<User>[]>(
    () => [
      { field: 'username', headerName: t('table.username'), flex: 1, minWidth: 140 },
      { field: 'email', headerName: t('table.email'), flex: 1, minWidth: 200 },
      {
        field: 'created_at',
        headerName: tCommon('fields.created_at'),
        width: TIMESTAMP_COLUMN_WIDTH,
        valueFormatter: (value: string) => formatDateTime(value),
      },
      rowActionsColumn<User>({
        count: 2,
        actions: ({ row }) => [
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
    [t, tCommon, dialog],
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
          density={grid.density}
          columnVisibilityModel={grid.columnVisibilityModel}
          onColumnVisibilityModelChange={grid.setColumnVisibilityModel}
          localeText={grid.localeText}
        />
      </Card>

      <UserFormDialog open={dialog.isCreateOpen} onClose={dialog.close} user={null} />

      <UserFormDialog open={dialog.isEditOpen} onClose={dialog.close} user={dialog.selected} />

      <ConfirmDialog
        open={dialog.isDeleteOpen}
        title={t('delete_title')}
        content={
          <>
            {t('messages.delete_confirm', { name: dialog.selected?.username ?? '' })}
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
