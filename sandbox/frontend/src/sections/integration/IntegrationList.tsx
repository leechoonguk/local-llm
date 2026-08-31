/**
 * Integration provider list — the list template, editing in place.
 *
 * A provider is configuration, not a record: its interesting content is the
 * operations and fields underneath it, so the row carries a detail button. It is
 * a button and not the row click because the row is editable — the same click
 * would have meant "open this" in one mode and "type here" in the other.
 * Its own columns are three scalars, which is exactly what a row editor holds —
 * a dialog for them would be a second surface asking for what the row already
 * shows. `code` is not among them: the server has no rename, so the column stays
 * read-only rather than accepting a value the API would ignore.
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Button, Card, Switch } from '@mui/material'
import { GridRowModes } from '@mui/x-data-grid'
import type { GridColDef, GridRowId, GridRowModesModel } from '@mui/x-data-grid'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListToolbar from '@/components/data-grid/ListToolbar'
import { rowActionsColumn } from '@/components/data-grid/RowActions'
import IntegrationDetailDialog from '@/sections/integration/IntegrationDetailDialog'
import IntegrationFormDialog, {
  BASE_URL_MAX_LENGTH,
  DISPLAY_NAME_MAX_LENGTH,
  HTTPS_ORIGIN_PATTERN,
} from '@/sections/integration/IntegrationFormDialog'
import Label from '@/components/label/Label'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import { useCrudDialog } from '@/hooks/useCrudDialog'
import { useDataGridState } from '@/hooks/useDataGridState'
import {
  useDeleteIntegration,
  useIntegrationList,
  useUpdateIntegration,
} from '@/lib/api/hooks/useIntegration'
import { usePagedRows } from '@/hooks/usePagedRows'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import type { Integration } from '@/types/integration'

const STATE_COLUMN_WIDTH = 110

const COUNT_COLUMN_WIDTH = 130

export default function IntegrationList() {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const query = useIntegrationList(grid.params)
  const { rows, rowCount, paginationMeta } = usePagedRows(
    query.data,
    grid.paginationModel.page,
    grid.paginationModel.pageSize,
  )
  const dialog = useCrudDialog<Integration>()
  const deleteMutation = useDeleteIntegration()
  const updateMutation = useUpdateIntegration()
  const [rowModes, setRowModes] = useState<GridRowModesModel>({})

  const startEdit = (id: GridRowId) =>
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.Edit } }))
  const commitEdit = (id: GridRowId) =>
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.View } }))
  const cancelEdit = (id: GridRowId) =>
    setRowModes((previous) => ({
      ...previous,
      [id]: { mode: GridRowModes.View, ignoreModifications: true },
    }))

  const columns = useMemo<GridColDef<Integration>[]>(
    () => [
      { field: 'code', headerName: t('table.code'), width: 160 },
      {
        field: 'display_name',
        headerName: t('table.display_name'),
        flex: 1,
        minWidth: 160,
        editable: true,
        // The same length the create form and the server enforce. An invalid cell
        // keeps the row in edit mode, so a 422 never has to explain it.
        preProcessEditCellProps: (params) => {
          const value = String(params.props.value ?? '').trim()
          return { ...params.props, error: value === '' || value.length > DISPLAY_NAME_MAX_LENGTH }
        },
      },
      {
        field: 'base_url',
        headerName: t('table.base_url'),
        flex: 1.5,
        minWidth: 220,
        editable: true,
        preProcessEditCellProps: (params) => {
          const value = String(params.props.value ?? '').trim()
          const invalid =
            value.length > BASE_URL_MAX_LENGTH || !HTTPS_ORIGIN_PATTERN.test(value)
          return { ...params.props, error: invalid }
        },
      },
      {
        field: 'enabled',
        headerName: t('table.enabled'),
        width: STATE_COLUMN_WIDTH,
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
         * appears nowhere else in the app: the read cell is a chip and both form
         * dialogs use a `Switch` for the same field. A switch also reads as the
         * state it is in, where a checkbox reads as a choice being ticked.
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
        field: 'operations',
        headerName: t('table.operations'),
        width: COUNT_COLUMN_WIDTH,
        align: 'center',
        headerAlign: 'center',
        sortable: false,
        renderCell: ({ row }) => row.operations.length,
      },
      rowActionsColumn<Integration>({
        count: 3,
        actions: ({ id, row }) =>
          rowModes[id]?.mode === GridRowModes.Edit
            ? [
                {
                  label: tCommon('actions.save'),
                  icon: 'check',
                  tone: 'primary',
                  onClick: () => commitEdit(id),
                },
                {
                  label: tCommon('actions.cancel'),
                  icon: 'close',
                  onClick: () => cancelEdit(id),
                },
              ]
            : [
                {
                  label: tCommon('actions.view'),
                  icon: 'view',
                  onClick: () => dialog.openView(row),
                },
                {
                  label: tCommon('actions.edit'),
                  icon: 'edit',
                  onClick: () => startEdit(id),
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
    [t, tCommon, dialog, rowModes],
  )

  /**
   * One PUT for the whole row, because that is the endpoint: `PUT /integration/{id}`
   * takes the resource, not a field. Returning the server's row is what puts the
   * new `version` in the grid; throwing is what makes the grid revert the cells
   * and keep the row open.
   */
  const handleRowUpdate = async (updated: Integration, original: Integration) => {
    const unchanged =
      updated.display_name === original.display_name &&
      updated.base_url === original.base_url &&
      updated.enabled === original.enabled
    if (unchanged) return original

    const saved = await updateMutation.mutateAsync({
      id: updated.id,
      data: {
        display_name: updated.display_name,
        base_url: updated.base_url,
        enabled: updated.enabled,
      },
    })
    toast.success(tCommon('messages.saved'))
    return saved
  }

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
          rowModesModel={rowModes}
          onRowModesModelChange={setRowModes}
          processRowUpdate={handleRowUpdate}
          onProcessRowUpdateError={(error) =>
            toast.error(serverErrorMessage(toApiError(error).code, tCommon))
          }
        />
      </Card>

      <IntegrationFormDialog open={dialog.isCreateOpen} onClose={dialog.close} />

      <IntegrationDetailDialog
        open={dialog.isViewOpen}
        onClose={dialog.close}
        integrationId={dialog.selected?.id ?? null}
      />

      <ConfirmDialog
        open={dialog.isDeleteOpen}
        title={t('delete_title')}
        content={
          <>
            {t('messages.delete_confirm', { name: dialog.selected?.display_name ?? '' })}
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
