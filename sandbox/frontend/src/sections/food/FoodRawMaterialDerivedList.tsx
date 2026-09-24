/**
 * The 원재료 list — a derived table the nightly derive job rebuilds and nobody edits here.
 *
 * The **derived list** shape (the 품목제조보고 list, copied):
 *   `useDataGridState`   → paging, density, column visibility
 *   `use<Domain>List`    → the page, refetched on mount and focus
 *   `useListFilters`     → one box per filterable column
 *   `useQueryErrorToast` → a failed read, reported the same way as everywhere
 *
 * No `useCrudDialog`, no `useToast`, no row edit and no add: the rows are a
 * function of the I2520 ledger, rewritten whole by `derive_food_tables` every
 * night, and the backend has no verb to accept one typed here.
 *
 * The row is the door: a material's synonym lists (이명·영문명·학명) run to a
 * thousand characters and its composition has siblings no column can hold, so
 * the grid shows the registry's own columns and the dialog the rest.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import Label from '@/components/label/Label'
import { TIMESTAMP_COLUMN_FLOOR } from '@/config'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useFoodRawMaterialFacets, useFoodRawMaterialList } from '@/lib/api/hooks/useFood'
import FoodRawMaterialDetailDialog from '@/sections/food/FoodRawMaterialDetailDialog'
import { formatDateTime } from '@/utils/formatTime'
import { USE_FLAGS } from '@/types/food'
import type { FoodRawMaterial, FoodRawMaterialListParams, UseFlag } from '@/types/food'

/**
 * Every column has a **floor** and a **share** (rule://frontend-screens, Column
 * Width). Floors are the widest measured value: a 14-character code, a class
 * name with its code in brackets (`건강기능식품(C코드)`), a one-word badge, the
 * shared timestamp; the representative name earns the most attention. The
 * eight that start visible total 1,060, inside the 1,080px card a 1440px
 * screen leaves beside the nav.
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  raw_material_code: { floor: 170, share: 0.8 },
  representative_raw_material_name: { floor: 217, share: 2 },
  raw_material_large_class: { floor: 170, share: 1 },
  raw_material_medium_class: { floor: 160, share: 0.8 },
  region_code_name: { floor: 100, share: 0.6 },
  process_code_name: { floor: 124, share: 0.6 },
  raw_material_status_code_name: { floor: 115, share: 0.6 },
  use_yn: { floor: 96, share: 0.4 },
  english_name: { floor: 160, share: 1 },
  scientific_name: { floor: 185, share: 1 },
  source_updated_at: { floor: TIMESTAMP_COLUMN_FLOOR, share: 1 },
}

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

/**
 * Columns a reader opens on purpose; the grid's selector brings them back.
 * The two synonym lists are long free text the dialog shows in full, so they
 * start hidden - they cost width and say little in a cell; the portal's
 * timestamp is on the dialog's audit line and the ninth column that would
 * push the grid into a horizontal scroll at 1440px.
 */
const HIDDEN_BY_DEFAULT: Record<string, boolean> = {
  english_name: false,
  scientific_name: false,
  source_updated_at: false,
}

/**
 * The columns this screen filters, in the order the boxes stand - the query
 * parameters' names, so a box and the parameter it sends cannot drift apart.
 * Three are free text and four are closed vocabularies; `SELECT_FIELDS`
 * names the second kind so the facets attach to the right boxes, and the use
 * flag is the one pair the schema closes (`UseFlag`), so its options are the
 * contract's constant and read through the locale.
 */
const FILTER_FIELDS = [
  'raw_material_code',
  'representative_raw_material_name',
  'raw_material_alias',
  'raw_material_large_class',
  'raw_material_medium_class',
  'raw_material_status_code_name',
  'use_yn',
] as const

const SELECT_FIELDS = [
  'raw_material_large_class',
  'raw_material_medium_class',
  'raw_material_status_code_name',
  'use_yn',
] as const

/** The one select whose options are codes, not the rows' own words. */
const CODE_FIELD = 'use_yn'

/**
 * A cascade: the medium class is a child of the large class, so once a parent
 * is chosen the child select offers only that parent's values (measured
 * 2026-09-09: 20 pairs over 5 parents and 17 children), and a child the new
 * parent does not have is cleared rather than left standing as a filter that
 * can match nothing. With no parent chosen the child offers every value. The
 * rule is the screen's, not the component's: `ListFilters` renders whatever
 * options it is handed, and which field narrows which lives beside the list.
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
  use_yn: 'raw_material.filter.use',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

type SelectField = (typeof SELECT_FIELDS)[number]

export default function FoodRawMaterialDerivedList() {
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
  const [openId, setOpenId] = useState<string | null>(null)

  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(facets, tCommon('messages.load_failed'))

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

  const { setColumnVisibilityModel } = grid
  useEffect(() => {
    setColumnVisibilityModel((current) => ({ ...HIDDEN_BY_DEFAULT, ...current }))
  }, [setColumnVisibilityModel])

  const columns = useMemo<GridColDef<FoodRawMaterial>[]>(
    () => [
      { ...sized('raw_material_code'), headerName: t('raw_material.table.code') },
      { ...sized('representative_raw_material_name'), headerName: t('raw_material.table.name') },
      { ...sized('raw_material_large_class'), headerName: t('raw_material.table.large_class') },
      { ...sized('raw_material_medium_class'), headerName: t('raw_material.table.medium_class') },
      { ...sized('region_code_name'), headerName: t('raw_material.table.region') },
      { ...sized('process_code_name'), headerName: t('raw_material.table.process') },
      { ...sized('raw_material_status_code_name'), headerName: t('raw_material.table.status') },
      {
        ...sized('use_yn'),
        headerName: t('raw_material.table.use'),
        // A code the portal closes (`Y`/`N`), read through the locale as a badge.
        renderCell: ({ row }) =>
          row.use_yn === null ? (
            '—'
          ) : (
            <Label variant="soft" color={row.use_yn === 'Y' ? 'success' : 'default'}>
              {row.use_yn === 'Y' ? t('raw_material.use.Y') : t('raw_material.use.N')}
            </Label>
          ),
      },
      { ...sized('english_name'), headerName: t('raw_material.table.english_name') },
      { ...sized('scientific_name'), headerName: t('raw_material.table.scientific_name') },
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
        reset={{
          label: tCommon('actions.reset'),
          onReset: filters.reset,
          disabled: !filters.isFiltered,
        }}
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
                : field === CODE_FIELD
                  ? USE_FLAGS
                  : field === CASCADE.child
                    ? childOptions
                    : (facets.data?.[field as Exclude<SelectField, typeof CODE_FIELD>] ?? []),
              // A code the schema closes is not a word: it reads through the locale.
              optionLabel:
                field === CODE_FIELD
                  ? (value) => t(`raw_material.use.${value as UseFlag}`)
                  : undefined,
            }))}
            values={filters.inputs}
            onChange={(name, value) => filters.setInput(name as FilterField, value)}
            allLabel={tCommon('filters.all')}
            noOptionsLabel={tCommon('filters.no_options')}
            clearLabel={tCommon('filters.clear')}
            openLabel={tCommon('filters.open')}
            closeLabel={tCommon('filters.close')}
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
        onRowClick={(row) => setOpenId(row.id)}
      />

      <FoodRawMaterialDetailDialog
        open={openId !== null}
        onClose={() => setOpenId(null)}
        rawMaterialId={openId}
      />
    </Card>
  )
}
