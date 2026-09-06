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
import { Card, Switch } from '@mui/material'
import { GridRowModes, useGridApiRef } from '@mui/x-data-grid'
import type { GridColDef, GridRowId, GridRowModesModel } from '@mui/x-data-grid'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
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
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import {
  useDeleteIntegration,
  useIntegrationList,
  useUpdateIntegration,
} from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import type { Integration, IntegrationListParams } from '@/types/integration'

/**
 * The columns this screen filters, in the order the boxes stand.
 *
 * The list is the query parameters' names, so a box, its label and the
 * parameter it sends cannot drift apart: a name the router does not read fails
 * `check-frontend-types` rather than filtering nothing quietly.
 */
const FILTER_FIELDS = ['code', 'display_name'] as const

type FilterField = (typeof FILTER_FIELDS)[number]

/** The columns a row edits, and what each can be wrong about. */
const EDITABLE_FIELDS = ['display_name', 'base_url'] as const

type EditableField = (typeof EDITABLE_FIELDS)[number]

interface FieldProblem {
  key:
    | 'validation.display_name_required'
    | 'validation.display_name_max'
    | 'validation.base_url_required'
    | 'validation.base_url_max'
    | 'validation.base_url_invalid'
  count?: number
}

const STATE_COLUMN_WIDTH = 110

const COUNT_COLUMN_WIDTH = 130

export default function IntegrationList() {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const apiRef = useGridApiRef()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<IntegrationListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useIntegrationList(params)
  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0
  const dialog = useCrudDialog<Integration>()
  const deleteMutation = useDeleteIntegration()
  const updateMutation = useUpdateIntegration()
  const [rowModes, setRowModes] = useState<GridRowModesModel>({})

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  const startEdit = (id: GridRowId) =>
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.Edit } }))
  /**
   * Why a row cannot be saved, in the words the reader gets — or `null`.
   *
   * One place, because the save button is not the only way out: pressing Enter
   * commits through the grid, and a rule enforced on the button alone would let
   * the keyboard past it into a 422 the server has to explain.
   */
  const refusal = (row: Integration): { field: EditableField; sentence: string } | null => {
    for (const field of EDITABLE_FIELDS) {
      const problem = problemOf(field, String(row[field] ?? ''))
      if (problem === null) continue
      return { field, sentence: t(problem.key, { count: problem.count ?? 0 }) }
    }
    return null
  }

  /**
   * Refusing a save says which cell refused, and puts the caret in it.
   *
   * The grid's own answer to an invalid row is to stay open, silently, so the
   * save button reads as broken. The focus move is deferred because the button
   * that was clicked takes focus back on its own mouse event.
   */
  const reportRefusal = (id: GridRowId, problem: { field: EditableField; sentence: string }) => {
    toast.error(problem.sentence)
    queueMicrotask(() => {
      apiRef.current?.setCellFocus(id, problem.field)
      apiRef.current?.getCellElement(id, problem.field)?.querySelector('input')?.focus()
    })
  }

  const commitEdit = (id: GridRowId) => {
    const row = apiRef.current?.getRowWithUpdatedValues(id, '') as Integration | undefined
    const problem = row === undefined ? null : refusal(row)
    if (problem !== null) {
      reportRefusal(id, problem)
      return
    }
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.View } }))
  }
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
        // The same rule the blocked save states in words, so a red cell and the
        // sentence can never disagree.
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: problemOf('display_name', String(params.props.value ?? '')) !== null,
        }),
      },
      {
        field: 'base_url',
        headerName: t('table.base_url'),
        flex: 1.5,
        minWidth: 220,
        editable: true,
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: problemOf('base_url', String(params.props.value ?? '')) !== null,
        }),
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, tCommon, dialog, rowModes],
  )

  /**
   * One PUT for the whole row, because that is the endpoint: `PUT /integration/{id}`
   * takes the resource, not a field. Returning the server's row is what puts the
   * new `version` in the grid; throwing is what makes the grid revert the cells
   * and keep the row open.
   */
  const handleRowUpdate = async (updated: Integration, original: Integration) => {
    const problem = refusal(updated)
    if (problem !== null) {
      reportRefusal(updated.id, problem)
      // Thrown so the grid keeps the row open; flagged so the error handler does
      // not say a second, vaguer thing about a failure already named.
      throw Object.assign(new Error(problem.sentence), { reported: true })
    }

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
        <ListCardHead
          title={t('list_title')}
          count={rowCount}
          add={{ label: tCommon('actions.add'), onAdd: dialog.openCreate }}
          refreshLabel={tCommon('actions.retry')}
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
          filters={
            <ListFilters
              fields={FILTER_FIELDS.map((field) => ({
                name: field,
                label: field === 'code' ? t('filter.code') : t('filter.display_name'),
              }))}
              values={filters.inputs}
              onChange={(name, value) => filters.setInput(name as FilterField, value)}
              isFiltered={filters.isFiltered}
              onReset={filters.reset}
              resetLabel={tCommon('actions.reset')}
            />
          }
        />

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
          rowModesModel={rowModes}
          onRowModesModelChange={setRowModes}
          processRowUpdate={handleRowUpdate}
          apiRef={apiRef}
          onProcessRowUpdateError={(error) => {
            if ((error as { reported?: boolean }).reported === true) return
            toast.error(serverErrorMessage(toApiError(error).code, tCommon))
          }}
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
        content={t('messages.delete_confirm', { name: dialog.selected?.display_name ?? '' })}
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
 * The one place a provider's editable value is judged.
 *
 * The red cell and the sentence a blocked save shows come from this function, so
 * a cell can never be red for a reason the message does not name, or refuse a
 * save the message calls fine. The rule carries its own wording rather than a
 * code the caller stitches to a field name: Korean joins the two with a
 * different particle per field.
 */
function problemOf(field: EditableField, value: string): FieldProblem | null {
  const trimmed = value.trim()
  if (field === 'display_name') {
    if (trimmed === '') return { key: 'validation.display_name_required' }
    return trimmed.length > DISPLAY_NAME_MAX_LENGTH
      ? { key: 'validation.display_name_max', count: DISPLAY_NAME_MAX_LENGTH }
      : null
  }
  if (trimmed === '') return { key: 'validation.base_url_required' }
  if (trimmed.length > BASE_URL_MAX_LENGTH) {
    return { key: 'validation.base_url_max', count: BASE_URL_MAX_LENGTH }
  }
  return HTTPS_ORIGIN_PATTERN.test(trimmed) ? null : { key: 'validation.base_url_invalid' }
}
