/**
 * The 업소 list — a derived table the nightly derive job rebuilds and nobody edits here.
 *
 * The **derived list** shape (the 원재료 list, copied):
 *   `useDataGridState`   → paging, density, column visibility
 *   `use<Domain>List`    → the page, refetched on mount and focus
 *   `useListFilters`     → one box per filterable column
 *   `useQueryErrorToast` → a failed read, reported the same way as everywhere
 *
 * No `useCrudDialog`, no `useToast`, no row edit and no add: the rows are a
 * function of eight business ledgers, rewritten whole by `derive_food_tables`
 * every night, and the backend has no verb to accept one typed here.
 *
 * The row is the door: a licence's neighbours - the rows sharing its name, the
 * licences on its site - are lists no cell can hold, so the grid shows the
 * registry's own columns and the dialog the rest.
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import Label from '@/components/label/Label'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useFoodBusinessFacets, useFoodBusinessList } from '@/lib/api/hooks/useFood'
import FoodBusinessDetailDialog from '@/sections/food/FoodBusinessDetailDialog'
import { formatPortalDate } from '@/utils/formatTime'
import { BUSINESS_STATUSES } from '@/types/food'
import type { BusinessStatus, FoodBusiness, FoodBusinessListParams } from '@/types/food'

/**
 * Every column has a **floor** and a **share** (rule://frontend-screens, Column
 * Width). Floors are the widest measured value of the live pass (2026-09-23):
 * an 11-digit 인허가번호, a 56-character 업소명, a 17-character 업종, the
 * one-word status badge, a 15-character 시·군·구, and two eight-digit dates
 * read as dates. The seven total 1,000, inside the 1,080px card a 1440px
 * screen leaves beside the nav.
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  license_no: { floor: 130, share: 0.8 },
  business_name: { floor: 200, share: 2 },
  industry_name: { floor: 150, share: 1 },
  status: { floor: 120, share: 0.5 },
  district: { floor: 140, share: 1 },
  permit_date: { floor: 140, share: 0.6 },
  closed_date: { floor: 120, share: 0.6 },
}

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

/**
 * The columns this screen filters, in the order the boxes stand - the query
 * parameters' names, so a box and the parameter it sends cannot drift apart.
 * Three are free text; the industry is a facets read (ten values in the live
 * pass) and the status is the pair the schema closes, so its options are the
 * contract's constant and read through the locale.
 */
const FILTER_FIELDS = [
  'business_name',
  'license_no',
  'district',
  'industry_name',
  'status',
] as const

const SELECT_FIELDS = ['industry_name', 'status'] as const

/** The one select whose options are codes, not the rows' own words. */
const CODE_FIELD = 'status'

const FILTER_LABEL_KEYS = {
  business_name: 'business.filter.business_name',
  license_no: 'business.filter.license_no',
  district: 'business.filter.district',
  industry_name: 'business.filter.industry_name',
  status: 'business.filter.status',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

type SelectField = (typeof SELECT_FIELDS)[number]

export default function FoodBusinessDerivedList() {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  const grid = useDataGridState()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<FoodBusinessListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useFoodBusinessList(params)
  const facets = useFoodBusinessFacets()
  const [openId, setOpenId] = useState<string | null>(null)

  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(facets, tCommon('messages.load_failed'))

  const columns = useMemo<GridColDef<FoodBusiness>[]>(
    () => [
      { ...sized('license_no'), headerName: t('business.table.license_no') },
      { ...sized('business_name'), headerName: t('business.table.business_name') },
      { ...sized('industry_name'), headerName: t('business.table.industry_name') },
      {
        ...sized('status'),
        headerName: t('business.table.status'),
        // Which ledger the row came from, read through the locale as a badge.
        renderCell: ({ row }) => (
          <Label variant="soft" color={row.status === 'ACTIVE' ? 'success' : 'default'}>
            {t(`business.status.${row.status}`)}
          </Label>
        ),
      },
      { ...sized('district'), headerName: t('business.table.district') },
      {
        ...sized('permit_date'),
        headerName: t('business.table.permit_date'),
        valueFormatter: (value: string | null) =>
          value === null ? '—' : formatPortalDate(value),
      },
      {
        ...sized('closed_date'),
        headerName: t('business.table.closed_date'),
        valueFormatter: (value: string | null) =>
          value === null ? '—' : formatPortalDate(value),
      },
    ],
    [t],
  )

  return (
    <Card>
      <ListCardHead
        title={t('business.list_title')}
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
              options: !SELECT_FIELDS.includes(field as SelectField)
                ? undefined
                : field === CODE_FIELD
                  ? BUSINESS_STATUSES
                  : (facets.data?.industry_name ?? []),
              // A code the schema closes is not a word: it reads through the locale.
              optionLabel:
                field === CODE_FIELD
                  ? (value) => t(`business.status.${value as BusinessStatus}`)
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

      <FoodBusinessDetailDialog
        open={openId !== null}
        onClose={() => setOpenId(null)}
        businessId={openId}
      />
    </Card>
  )
}
