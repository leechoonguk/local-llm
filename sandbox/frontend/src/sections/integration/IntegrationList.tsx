/**
 * Integration provider list — the list template, editing in place.
 *
 * A provider is configuration, not a record: its interesting content is the
 * operations, the credentials and the call log underneath it, so **the row is
 * the door** to them — the same shape the batch list carries
 * (rule://product-areas, Pattern: operations). The door is safe beside the
 * editors because `ServerDataGrid` guards it: a row in edit mode has no door,
 * and a click inside the actions cell belongs to its button. No detail button
 * stands beside it — one intent, one control.
 * Its own columns are three scalars, which is exactly what a row editor holds —
 * a dialog for them would be a second surface asking for what the row already
 * shows. `code` is not among them: the server has no rename, so the column stays
 * read-only rather than accepting a value the API would ignore.
 */

import { useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, Switch } from '@mui/material'
import { useGridApiRef } from '@mui/x-data-grid'
import type { GridColDef } from '@mui/x-data-grid'
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
import { useRowEditor } from '@/hooks/useRowEditor'
import type { RowRefusal } from '@/hooks/useRowEditor'
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

const FILTER_LABEL_KEYS = {
  code: 'filter.code',
  display_name: 'filter.display_name',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

/**
 * Every column has a **floor** and a **share** (rule://frontend-screens, Column
 * Width). Floors are the widest measured value: a 22-character provider code
 * (`mfds-food-safety-korea`), a 34-character base URL, a one-word badge, a
 * two-digit count; the URL earns the most attention, the name next.
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  code: { floor: 200, share: 0.8 },
  display_name: { floor: 160, share: 1 },
  base_url: { floor: 260, share: 1.5 },
  enabled: { floor: 110, share: 0.4 },
  operations: { floor: 148, share: 0.4 },
}

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

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

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  /**
   * Why a row cannot be saved, in the words the reader gets — or `null`.
   *
   * The screen owns this and `problemOf`; `useRowEditor` owns what is done with
   * the answer, which is the same on every screen that edits in place.
   */
  const refusal = useCallback(
    (row: Integration): RowRefusal<EditableField> | null => {
      for (const field of EDITABLE_FIELDS) {
        const problem = problemOf(field, String(row[field] ?? ''))
        if (problem === null) continue
        return { field, sentence: t(problem.key, { count: problem.count ?? 0 }) }
      }
      return null
    },
    [t],
  )
  const editor = useRowEditor<Integration, EditableField>({ apiRef, refusal })

  const columns = useMemo<GridColDef<Integration>[]>(
    () => [
      { ...sized('code'), headerName: t('table.code') },
      {
        ...sized('display_name'),
        headerName: t('table.display_name'),
        editable: true,
        // The same rule the blocked save states in words, so a red cell and the
        // sentence can never disagree.
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: problemOf('display_name', String(params.props.value ?? '')) !== null,
        }),
      },
      {
        ...sized('base_url'),
        headerName: t('table.base_url'),
        editable: true,
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: problemOf('base_url', String(params.props.value ?? '')) !== null,
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
        ...sized('operations'),
        headerName: t('table.operations'),
        align: 'center',
        headerAlign: 'center',
        sortable: false,
        renderCell: ({ row }) => row.operations.length,
      },
      rowActionsColumn<Integration>({
        count: 2,
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
    [t, tCommon, dialog, editor],
  )

  /**
   * One PUT for the whole row, because that is the endpoint: `PUT /integration/{id}`
   * takes the resource, not a field. Returning the server's row is what puts the
   * new `version` in the grid; throwing is what makes the grid revert the cells
   * and keep the row open.
   */
  const handleRowUpdate = editor.guardRowUpdate(async (updated: Integration, original: Integration) => {
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
              fields={FILTER_FIELDS.map((field) => ({
                name: field,
                label: t(FILTER_LABEL_KEYS[field]),
              }))}
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
          onRowClick={(row) => dialog.openView(row)}
          rowModesModel={editor.rowModes}
          onRowModesModelChange={editor.setRowModes}
          processRowUpdate={handleRowUpdate}
          apiRef={apiRef}
          onProcessRowUpdateError={(error) =>
            editor.rowUpdateError(error, (failure) => serverErrorMessage(toApiError(failure).code, tCommon))
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
