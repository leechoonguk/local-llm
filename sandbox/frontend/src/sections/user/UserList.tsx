/**
 * The user list — a table that is also the form, the way the integration screen edits.
 *
 * Five hooks in a fixed order, and nothing else decides state:
 *   `useDataGridState`   → paging, density, column visibility
 *   `use<Domain>List`    → the page, cached and invalidated by the hooks layer
 *   `useCrudDialog`      → which dialog is open and on which row
 *   `useToast`           → the outcome of a mutation
 *   `useQueryErrorToast` → a failed read, reported the same way
 *
 * The screen owns presentation: columns, the empty sentence, and which dialogs
 * exist. It never builds a query key, a URL or an axios call.
 *
 * **A user is three scalars, which is exactly what a row holds.** So there is no
 * form dialog on this screen at all: `+` puts an empty row at the top of the
 * grid in edit mode, and saving it is a create; the pencil opens an existing row
 * the same way, and saving it is an update. A dialog for these fields would be a
 * second surface asking for what the row already shows, and it would ask in a
 * different order and with different lengths the moment either side changed.
 *
 * `+` is an icon beside refresh rather than a labelled button, because it is now
 * an operation *on the table* — it adds a row to it — and the table's operations
 * are icons on the table's own row. Its head carries what decides the rows: the
 * filters, refresh, and the one control that adds one.
 *
 * There is no density control: it changed how the rows look and nothing about
 * what they are, and the row it sat in is now the filters'.
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@mui/material'
import { GridEditInputCell, GridRowModes, useGridApiRef } from '@mui/x-data-grid'
import type { GridColDef, GridRowId, GridRowModesModel } from '@mui/x-data-grid'
import ConfirmDialog from '@/components/confirm-dialog/ConfirmDialog'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import { rowActionsColumn } from '@/components/data-grid/RowActions'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import { useCrudDialog } from '@/hooks/useCrudDialog'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useToast } from '@/hooks/useToast'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import { useCreateUser, useDeleteUser, useUpdateUser, useUserList } from '@/lib/api/hooks/useUser'
import { formatDateTime } from '@/utils/formatTime'
import type { User, UserListParams } from '@/types/user'

const TIMESTAMP_COLUMN_WIDTH = 180

const PASSWORD_COLUMN_WIDTH = 160

/** Lengths and the shape of an address, as the user schemas declare them. */
const USERNAME_MAX_LENGTH = 50

const EMAIL_MAX_LENGTH = 255

const PASSWORD_MIN_LENGTH = 8

const PASSWORD_MAX_LENGTH = 128

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/**
 * What a cell is wrong about, or `null` — as the sentence the reader will see.
 *
 * The rule carries its own wording instead of a code the caller stitches to a
 * field name: `비밀번호: 8자 이상 입력하세요` is two fragments and a colon where
 * Korean wants one sentence, and the particle that joins them differs per field
 * (`사용자명을`, `비밀번호는`). One key per rule, written out in the locale.
 */
interface FieldProblem {
  key:
    | 'validation.username_required'
    | 'validation.username_max'
    | 'validation.email_required'
    | 'validation.email_invalid'
    | 'validation.email_max'
    | 'validation.password_required'
    | 'validation.password_min'
    | 'validation.password_max'
  count?: number
}

const EDITABLE_FIELDS = ['username', 'email', 'password'] as const

type EditableField = (typeof EDITABLE_FIELDS)[number]

/** What a saved row shows in the password cell: a secret the API never returns. */
const PASSWORD_MASK = '••••••••'

/**
 * The columns this screen filters, in the order the boxes stand.
 *
 * The list is the query parameters' names (`username`, `email`), so a box, its
 * label and the parameter it sends cannot drift apart: adding a filterable
 * column here is what puts a box on screen, and a name the router does not read
 * fails `check-frontend-types` rather than filtering nothing quietly.
 */
const FILTER_FIELDS = ['username', 'email'] as const

type FilterField = (typeof FILTER_FIELDS)[number]

/**
 * A grid row: a saved user, or the one being created, plus the password cell.
 *
 * `password` is never a `User` — the API does not return it — so it lives only
 * on the row. `isNew` is what makes saving a create instead of an update: the
 * row carries its own verb, and a draft that is cancelled is dropped rather than
 * reverted to a version of itself that was never stored.
 */
interface UserRow extends User {
  password: string
  isNew?: boolean
}

const toRow = (user: User): UserRow => ({ ...user, password: '' })

const draftRow = (): UserRow => ({
  id: crypto.randomUUID(),
  username: '',
  email: '',
  password: '',
  created_by: null,
  updated_by: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  version: 0,
  isNew: true,
})

export default function UserList() {
  const { t } = useTranslation('user')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const grid = useDataGridState()
  const apiRef = useGridApiRef()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const [draft, setDraft] = useState<UserRow | null>(null)
  const [rowModes, setRowModes] = useState<GridRowModesModel>({})
  /**
   * Rows whose save was refused, and therefore the rows allowed to look wrong.
   *
   * A cell turns red once it has been typed into or once someone has claimed the
   * row is finished — never on a row that just opened. An empty new row is not a
   * row of mistakes; painting all three cells red before the first keystroke
   * says it is.
   */
  const [refused, setRefused] = useState<ReadonlySet<GridRowId>>(new Set())
  const params = useMemo<UserListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useUserList(params)
  /**
   * The draft is a row of this page, so it is counted as one: a total that
   * ignored it would say "1-10 of 10" over eleven rows, and the footer is what a
   * reader trusts about how much data there is.
   */
  const rows = useMemo<UserRow[]>(() => {
    const saved = (query.data?.items ?? []).map(toRow)
    return draft === null ? saved : [draft, ...saved]
  }, [query.data?.items, draft])
  const rowCount = (query.data?.total ?? 0) + (draft === null ? 0 : 1)
  const dialog = useCrudDialog<User>()
  const createMutation = useCreateUser()
  const updateMutation = useUpdateUser()
  const deleteMutation = useDeleteUser()

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  /**
   * `true` when the cell should *show* it is wrong, which is not the same as
   * being wrong: the value is judged by `problemOf` either way, and the commit
   * is gated on that; this only decides whether the reader is being told yet.
   */
  const showsProblem = (params: {
    id: GridRowId
    field: EditableField
    value: string
    stored: string
    isNew: boolean
  }) => {
    if (problemOf(params.field, params.value, params.isNew) === null) return false
    return params.value !== params.stored || refused.has(params.id)
  }

  const startEdit = (id: GridRowId) =>
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.Edit } }))
  /**
   * Saving says why it cannot, on the cell that cannot.
   *
   * The grid's own answer to an invalid row is to refuse the commit and stay
   * open — silently, so the save button reads as broken. The pending values live
   * in the grid's edit state, which is why the screen holds `apiRef`: it judges
   * the row by the same rule the cells use, names the first field that fails,
   * and puts the caret in it. Nothing is said while typing — a field is wrong
   * only once someone claims it is finished.
   */
  /**
   * Why a row cannot be saved, in the words the reader gets — or `null`.
   *
   * One place, because the save button is not the only way out: pressing Enter
   * commits through the grid, and a rule enforced on the button alone would let
   * the keyboard past it into a 422 the server has to explain.
   */
  const refusal = (row: UserRow): { field: EditableField; sentence: string } | null => {
    for (const field of EDITABLE_FIELDS) {
      const problem = problemOf(field, String(row[field] ?? ''), row.isNew === true)
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
   * that was clicked takes focus back on its own mouse event — measured: the
   * toast named a cell three columns from where the caret stayed.
   */
  const reportRefusal = (id: GridRowId, problem: { field: EditableField; sentence: string }) => {
    setRefused((previous) => new Set(previous).add(id))
    toast.error(problem.sentence)
    queueMicrotask(() => {
      apiRef.current?.setCellFocus(id, problem.field)
      apiRef.current?.getCellElement(id, problem.field)?.querySelector('input')?.focus()
    })
  }

  const forgetRefusal = (id: GridRowId) =>
    setRefused((previous) => {
      if (!previous.has(id)) return previous
      const next = new Set(previous)
      next.delete(id)
      return next
    })

  const commitEdit = (id: GridRowId) => {
    const row = apiRef.current?.getRowWithUpdatedValues(id, '') as UserRow | undefined
    const problem = row === undefined ? null : refusal(row)
    if (problem !== null) {
      reportRefusal(id, problem)
      return
    }
    forgetRefusal(id)
    setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.View } }))
  }

  /**
   * Cancelling a draft removes it; cancelling a saved row restores it. Reverting
   * a draft would leave an empty row in the table that no endpoint has ever
   * heard of.
   */
  const cancelEdit = (id: GridRowId) => {
    forgetRefusal(id)
    setRowModes((previous) => ({
      ...previous,
      [id]: { mode: GridRowModes.View, ignoreModifications: true },
    }))
    /**
     * The draft is dropped in the update *after* the one that ends its edit.
     *
     * Removed in the same update, the grid was still stopping an editor whose
     * row had already vanished and fell back to committing it: cancelling a new
     * row POSTed the empty draft and answered 422, with an error toast for a
     * write nobody asked for (measured on this screen, twice — the second time
     * by deriving the row's presence from its mode, which is the same update).
     */
    if (draft?.id === id) queueMicrotask(() => setDraft(null))
  }

  const startCreate = () => {
    const row = draftRow()
    setDraft(row)
    grid.resetPage()
    setRowModes((previous) => ({
      ...previous,
      [row.id]: { mode: GridRowModes.Edit, fieldToFocus: 'username' },
    }))
  }

  const columns = useMemo<GridColDef<UserRow>[]>(
    () => [
      {
        field: 'username',
        headerName: t('table.username'),
        flex: 1,
        minWidth: 140,
        editable: true,
        // The same lengths the server enforces. An invalid cell keeps the row in
        // edit mode, so a 422 never has to explain it.
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: showsProblem({
            id: params.id,
            field: 'username',
            value: String(params.props.value ?? ''),
            stored: String(params.row.username ?? ''),
            isNew: params.row.isNew === true,
          }),
        }),
      },
      {
        field: 'email',
        headerName: t('table.email'),
        flex: 1,
        minWidth: 200,
        editable: true,
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: showsProblem({
            id: params.id,
            field: 'email',
            value: String(params.props.value ?? ''),
            stored: String(params.row.email ?? ''),
            isNew: params.row.isNew === true,
          }),
        }),
      },
      {
        field: 'password',
        headerName: t('table.password'),
        width: PASSWORD_COLUMN_WIDTH,
        sortable: false,
        editable: true,
        /**
         * A saved row shows the mask, never a value: the API does not return the
         * password, so an empty cell would read as "this account has none".
         * Typing into it sets a new one; leaving it empty keeps the stored one,
         * which is what the server means by an omitted `password`.
         */
        renderCell: ({ row }) => (row.isNew === true ? '' : PASSWORD_MASK),
        /**
         * The grid's own editor with the characters hidden, not a `TextField`
         * dressed to look like one.
         *
         * A standard `TextField` here was a different box: its line sat half a
         * pixel below the lines in the cells beside it and its text started 16px
         * further left, and each attempt to match the metrics by hand landed on
         * a new fraction (450.4, then 449.4, against 449.9). Rendering what the
         * other cells render makes the alignment a fact rather than a number to
         * maintain, and the invalid state comes with it.
         */
        renderEditCell: (params) => <GridEditInputCell {...params} type="password" />,
        preProcessEditCellProps: (params) => ({
          ...params.props,
          error: showsProblem({
            id: params.id,
            field: 'password',
            value: String(params.props.value ?? ''),
            stored: '',
            isNew: (params.row as UserRow).isNew === true,
          }),
        }),
      },
      {
        field: 'created_at',
        headerName: tCommon('fields.created_at'),
        width: TIMESTAMP_COLUMN_WIDTH,
        // A draft has no creation time until the server gives it one, and a
        // date rendered from `new Date()` would claim it already has.
        renderCell: ({ row }) => (row.isNew === true ? '—' : formatDateTime(row.created_at)),
      },
      rowActionsColumn<UserRow>({
        count: 2,
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
    [t, tCommon, dialog, rowModes, draft, refused],
  )

  /**
   * One row, one write, and which write is the row's own answer.
   *
   * Returning the saved row is what puts the server's `id` and `version` in the
   * grid; throwing is what makes the grid revert the cells and keep the row
   * open, which is the only way a rejected save stays fixable in place.
   */
  const handleRowUpdate = async (updated: UserRow): Promise<UserRow> => {
    const problem = refusal(updated)
    if (problem !== null) {
      reportRefusal(updated.id, problem)
      // Thrown so the grid keeps the row open; flagged so the error handler does
      // not say a second, vaguer thing about a failure already named.
      throw Object.assign(new Error(problem.sentence), { reported: true })
    }

    if (updated.isNew === true) {
      const created = await createMutation.mutateAsync({
        username: updated.username.trim(),
        email: updated.email.trim(),
        password: updated.password,
      })
      setDraft(null)
      toast.success(tCommon('messages.created'))
      return toRow(created)
    }

    const saved = await updateMutation.mutateAsync({
      id: updated.id,
      data: {
        username: updated.username.trim(),
        email: updated.email.trim(),
        password: updated.password === '' ? undefined : updated.password,
      },
    })
    toast.success(tCommon('messages.saved'))
    return toRow(saved)
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
          add={{ label: tCommon('actions.add'), onAdd: startCreate, disabled: draft !== null }}
          refreshLabel={tCommon('actions.retry')}
          onRefresh={() => void query.refetch()}
          refreshing={query.isFetching}
          filters={
            <ListFilters
              fields={FILTER_FIELDS.map((field) => ({
                name: field,
                label: field === 'username' ? t('filter.username') : t('filter.email'),
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
          apiRef={apiRef}
          rowModesModel={rowModes}
          onRowModesModelChange={setRowModes}
          processRowUpdate={handleRowUpdate}
          onProcessRowUpdateError={(error) => {
            if ((error as { reported?: boolean }).reported === true) return
            toast.error(serverErrorMessage(toApiError(error).code, tCommon))
          }}
        />
      </Card>

      <ConfirmDialog
        open={dialog.isDeleteOpen}
        title={t('delete_title')}
        content={t('messages.delete_confirm', { name: dialog.selected?.username ?? '' })}
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
 * The one place a value is judged.
 *
 * The red cell and the sentence a blocked save shows come from this function, so
 * a cell can never be red for a reason the message does not name, or refuse a
 * save the message calls fine.
 */
function problemOf(field: EditableField, value: string, isNew: boolean): FieldProblem | null {
  const trimmed = field === 'password' ? value : value.trim()
  if (field === 'username') {
    if (trimmed === '') return { key: 'validation.username_required' }
    return trimmed.length > USERNAME_MAX_LENGTH
      ? { key: 'validation.username_max', count: USERNAME_MAX_LENGTH }
      : null
  }
  if (field === 'email') {
    if (trimmed === '') return { key: 'validation.email_required' }
    if (trimmed.length > EMAIL_MAX_LENGTH) {
      return { key: 'validation.email_max', count: EMAIL_MAX_LENGTH }
    }
    return EMAIL_PATTERN.test(trimmed) ? null : { key: 'validation.email_invalid' }
  }
  // An empty password keeps the stored one, which a new row does not have.
  if (trimmed === '') return isNew ? { key: 'validation.password_required' } : null
  if (trimmed.length < PASSWORD_MIN_LENGTH) {
    return { key: 'validation.password_min', count: PASSWORD_MIN_LENGTH }
  }
  return trimmed.length > PASSWORD_MAX_LENGTH
    ? { key: 'validation.password_max', count: PASSWORD_MAX_LENGTH }
    : null
}
