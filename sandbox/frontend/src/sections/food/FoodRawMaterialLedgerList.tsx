/**
 * The raw material ledger — a list a nightly sync fills and nobody edits here.
 *
 * The **ledger list** shape: the list template with its write half removed.
 *   `useDataGridState`   → paging, density, column visibility
 *   `use<Domain>List`    → the page, refetched on mount and focus
 *   `useListFilters`     → one box per filterable column
 *   `useQueryErrorToast` → a failed read, reported the same way as everywhere
 *
 * No `useCrudDialog`, no `useToast`, no row actions and no add: the rows are the
 * provider's, copied by `sync_food_raw_material_ledger` every night and compared
 * against the provider on every pass. A row typed here would be overwritten by
 * morning, and the backend has no verb to accept it. What the screen owns is
 * still presentation - which columns, the empty sentence - and it never builds a
 * query key, a URL or an axios call.
 *
 * Every column of the ledger is a grid column, so there is no detail dialog and
 * no GET-by-id: the grid's own column selector is the detail view. The names
 * few readers scan for (English, scientific, region, process) start hidden and
 * the rest start shown - `HIDDEN_BY_DEFAULT` is merged into the grid's model on
 * first render so the reader's own choices are kept afterwards.
 *
 * The long columns (`raw_material_alias` reaches 1,130 characters - it is a
 * synonym list the portal joins into one string) render through `ClippedText`,
 * so a row stays one line tall and the full value is a hover away.
 */

import { useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import ClippedText from '@/components/detail/ClippedText'
import Label from '@/components/label/Label'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useFoodRawMaterialFacets, useFoodRawMaterialList } from '@/lib/api/hooks/useFood'
import { formatDateTime } from '@/utils/formatTime'
import type { FoodRawMaterial, FoodRawMaterialListParams } from '@/types/food'

/**
 * Every column has a **floor** and a **share**, and spare width is spread by
 * share across all of them - not piled into one or two.
 *
 * With `flex` on two columns only, a 1920px screen put ~550px into the name and
 * ~270px into the mostly-empty alias while `식품원료(A코드)` was still clipped
 * three columns to the right. The floor is the width at which the column's
 * widest measured value stops clipping (14-character codes, `식품원료(A코드)`,
 * a localised timestamp); the share is how much of a reader's attention the
 * column earns: the name most, codes and the timestamp a full share, short
 * vocabularies and flags less. At 1400px every visible column sits on its
 * floor and nothing clips; wider, they all grow, in proportion.
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  raw_material_code: { floor: 170, share: 1 },
  representative_raw_material_name: { floor: 180, share: 2 },
  raw_material_alias: { floor: 120, share: 1.2 },
  english_name: { floor: 120, share: 1.2 },
  scientific_name: { floor: 120, share: 1.2 },
  raw_material_large_class: { floor: 160, share: 1 },
  raw_material_medium_class: { floor: 130, share: 0.8 },
  region_code: { floor: 90, share: 0.4 },
  region_code_name: { floor: 130, share: 0.8 },
  process_code: { floor: 90, share: 0.4 },
  process_code_name: { floor: 130, share: 0.8 },
  raw_material_status_code: { floor: 90, share: 0.4 },
  raw_material_status_code_name: { floor: 100, share: 0.6 },
  valid_start_date: { floor: 110, share: 0.6 },
  valid_end_date: { floor: 110, share: 0.6 },
  use_yn: { floor: 80, share: 0.4 },
  source_updated_at: { floor: 185, share: 1 },
}

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

/**
 * Columns a reader opens on purpose; the grid's selector brings them back.
 * The validity dates are placeholders on most rows (`19000101` / `99991231`)
 * and `use_yn` is already the status chip's colour, so all three start hidden -
 * they cost width and say little. Measured at 1400px with them shown: the code
 * and the timestamp clipped; with them hidden, nothing does.
 */
const HIDDEN_BY_DEFAULT: Record<string, boolean> = {
  valid_start_date: false,
  valid_end_date: false,
  use_yn: false,
  english_name: false,
  scientific_name: false,
  region_code: false,
  region_code_name: false,
  process_code: false,
  process_code_name: false,
  raw_material_status_code: false,
}

/**
 * The columns this screen filters, in the order the boxes stand - the query
 * parameters' names, so a box and the parameter it sends cannot drift apart.
 *
 * Three are free text and three are closed vocabularies; which is which is the
 * column's nature, and `SELECT_FIELDS` names the second kind so the boxes are
 * built from one list and the facets are attached to the right three.
 */
const FILTER_FIELDS = [
  'raw_material_code',
  'representative_raw_material_name',
  'raw_material_alias',
  'raw_material_large_class',
  'raw_material_medium_class',
  'raw_material_status_code_name',
] as const

const SELECT_FIELDS = [
  'raw_material_large_class',
  'raw_material_medium_class',
  'raw_material_status_code_name',
] as const

/**
 * A cascade: the medium class is a child of the large class, so once a parent is
 * chosen the child select offers only that parent's values (measured: 1 to 8
 * each, against 30 in all), and a child the new parent does not have is cleared
 * rather than left standing as a filter that can match nothing. With no parent
 * chosen the child offers every value. The rule is the screen's, not the
 * component's: `ListFilters` renders whatever options it is handed, and which
 * field narrows which is domain knowledge that lives beside the field list.
 */
const CASCADE = {
  parent: 'raw_material_large_class',
  child: 'raw_material_medium_class',
} as const

const FILTER_LABEL_KEYS = {
  raw_material_code: 'raw_material.filter.code',
  representative_raw_material_name: 'raw_material.filter.name',
  raw_material_alias: 'raw_material.filter.alias',
  raw_material_large_class: 'raw_material.filter.large_class',
  raw_material_medium_class: 'raw_material.filter.medium_class',
  raw_material_status_code_name: 'raw_material.filter.status',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

type SelectField = (typeof SELECT_FIELDS)[number]

export default function FoodRawMaterialLedgerList() {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  const grid = useDataGridState()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<FoodRawMaterialListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useFoodRawMaterialList(params)
  const facets = useFoodRawMaterialFacets()

  const parentValue = filters.inputs[CASCADE.parent]
  const childOptions = useMemo<readonly string[]>(() => {
    if (facets.data === undefined) return []
    if (parentValue === '') return facets.data.raw_material_medium_class
    return facets.data.raw_material_medium_class_by_large[parentValue] ?? []
  }, [facets.data, parentValue])

  const childValue = filters.inputs[CASCADE.child]
  const { setInput } = filters
  useEffect(() => {
    if (childValue !== '' && facets.data !== undefined && !childOptions.includes(childValue)) {
      setInput(CASCADE.child, '')
    }
  }, [childValue, childOptions, facets.data, setInput])
  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  const { setColumnVisibilityModel } = grid
  useEffect(() => {
    setColumnVisibilityModel((current) => ({ ...HIDDEN_BY_DEFAULT, ...current }))
  }, [setColumnVisibilityModel])

  const columns = useMemo<GridColDef<FoodRawMaterial>[]>(
    () => [
      { ...sized('raw_material_code'), headerName: t('raw_material.table.code') },
      {
        ...sized('representative_raw_material_name'),
        headerName: t('raw_material.table.name'),
      },
      {
        ...sized('raw_material_alias'),
        headerName: t('raw_material.table.alias'),
        sortable: false,
        renderCell: ({ value }) => <ClippedText text={String(value ?? '')} />,
      },
      {
        ...sized('english_name'),
        headerName: t('raw_material.table.english_name'),
        sortable: false,
        renderCell: ({ value }) => <ClippedText text={String(value ?? '')} />,
      },
      {
        ...sized('scientific_name'),
        headerName: t('raw_material.table.scientific_name'),
        sortable: false,
        renderCell: ({ value }) => <ClippedText text={String(value ?? '')} />,
      },
      {
        ...sized('raw_material_large_class'),
        headerName: t('raw_material.table.large_class'),
      },
      {
        ...sized('raw_material_medium_class'),
        headerName: t('raw_material.table.medium_class'),
      },
      { ...sized('region_code'), headerName: t('raw_material.table.region_code') },
      {
        ...sized('region_code_name'),
        headerName: t('raw_material.table.region'),
      },
      { ...sized('process_code'), headerName: t('raw_material.table.process_code') },
      {
        ...sized('process_code_name'),
        headerName: t('raw_material.table.process'),
      },
      {
        ...sized('raw_material_status_code'),
        headerName: t('raw_material.table.status_code'),
      },
      {
        ...sized('raw_material_status_code_name'),
        headerName: t('raw_material.table.status'),
        renderCell: ({ row }) =>
          row.raw_material_status_code_name === null ? (
            '—'
          ) : (
            <Label variant="soft" color={row.use_yn === 'Y' ? 'success' : 'default'}>
              {row.raw_material_status_code_name}
            </Label>
          ),
      },
      {
        ...sized('valid_start_date'),
        headerName: t('raw_material.table.valid_start'),
      },
      {
        ...sized('valid_end_date'),
        headerName: t('raw_material.table.valid_end'),
      },
      { ...sized('use_yn'), headerName: t('raw_material.table.use_yn') },
      {
        ...sized('source_updated_at'),
        headerName: t('raw_material.table.source_updated_at'),
        renderCell: ({ value }) => (value === null ? '—' : formatDateTime(String(value))),
      },
    ],
    [t],
  )

  return (
    <Card>
      <ListCardHead
        title={t('raw_material.list_title')}
        count={rowCount}
        refreshLabel={tCommon('actions.retry')}
        onRefresh={() => void query.refetch()}
        refreshing={query.isFetching}
        filters={
          <ListFilters
            fields={FILTER_FIELDS.map((field) => ({
              name: field,
              label: t(FILTER_LABEL_KEYS[field]),
              // A select while its options are loading is a select with one
              // entry, "all" - it never falls back to a text box, which would
              // send a contains-match the router answers with equals.
              options: !SELECT_FIELDS.includes(field as SelectField)
                ? undefined
                : field === CASCADE.child
                  ? childOptions
                  : (facets.data?.[field as SelectField] ?? []),
            }))}
            values={filters.inputs}
            onChange={(name, value) => filters.setInput(name as FilterField, value)}
            isFiltered={filters.isFiltered}
            onReset={filters.reset}
            resetLabel={tCommon('actions.reset')}
            allLabel={tCommon('filters.all')}
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
      />
    </Card>
  )
}
