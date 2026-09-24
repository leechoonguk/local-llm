/**
 * The 품목제조보고 list — a derived table the nightly derive job rebuilds and nobody edits here.
 *
 * The **derived list** shape: the list template with its write half removed.
 *   `useDataGridState`   → paging, density, column visibility
 *   `use<Domain>List`    → the page, refetched on mount and focus
 *   `useListFilters`     → one box per filterable column
 *   `useQueryErrorToast` → a failed read, reported the same way as everywhere
 *
 * No `useCrudDialog`, no `useToast`, no row edit and no add: the rows are a
 * function of the ledgers, rewritten whole by `derive_food_tables` every night.
 * A row typed here would be gone by morning, and the backend has no verb to
 * accept it. What the screen owns is presentation - which columns, the empty
 * sentence, the row as the one door - and it never builds a query key, a URL
 * or an axios call.
 *
 * The row itself opens the detail dialog: a report has three edges (the 공전
 * type it names, its label's ingredients, its nutrition) that no grid column
 * can hold, so the grid shows the registry's own columns and the dialog the
 * rest. No actions column - a row nobody edits has one verb, and the row is
 * it. Livestock rows carry NULL in the eleven columns C006 does not publish;
 * those start hidden and the grid's selector brings them back.
 */

import { useEffect, useMemo, useState } from 'react'
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
import { TIMESTAMP_COLUMN_FLOOR } from '@/config'
import { useFoodItemReportFacets, useFoodItemReportList } from '@/lib/api/hooks/useFood'
import FoodItemReportDetailDialog from '@/sections/food/FoodItemReportDetailDialog'
import { formatDateTime, formatPortalDate } from '@/utils/formatTime'
import { REPORT_KINDS } from '@/types/food'
import type { FoodItemReport, FoodItemReportListParams, ReportKind } from '@/types/food'

/**
 * Every column has a **floor** and a **share**, and spare width is spread by
 * share across all of them - not piled into one or two. The floor is the width
 * at which the column's widest value stops clipping (a 16-digit registry
 * number, `식품제조가공업`, a localised timestamp); the share is how much of a
 * reader's attention the column earns: the product name most, names and the
 * timestamp a full share, flags and dates less. What an authority published
 * about a product is not here: 946 events over 1.9M rows is a column that is
 * zero on 99.95% of them, and they have a screen of their own (2026-09-15).
 */
const COLUMN: Record<string, { floor: number; share: number }> = {
  report_kind: { floor: 204, share: 0.4 },
  item_report_no: { floor: 170, share: 1 },
  product_name: { floor: 200, share: 2 },
  product_type_name: { floor: 140, share: 1 },
  business_name: { floor: 209, share: 1.2 },
  license_no: { floor: 147, share: 0.8 },
  report_date: { floor: 152, share: 0.6 },
  maker_name: { floor: 165, share: 1 },
  origin_country: { floor: 237, share: 0.5 },
  product_name_en: { floor: 194, share: 1 },
  industry_name: { floor: 140, share: 0.8 },
  shelf_life: { floor: 144, share: 1 },
  product_form: { floor: 120, share: 1 },
  packaging_material: { floor: 140, share: 1 },
  usage_method: { floor: 120, share: 1 },
  purpose: { floor: 124, share: 1 },
  quality_maintenance_days: { floor: 160, share: 0.6 },
  production_ended: { floor: 193, share: 0.5 },
  high_calorie_low_nutrition: { floor: 269, share: 0.5 },
  child_favorite_certified_yn: { floor: 221, share: 0.4 },
  domestic_export_type: { floor: 185, share: 0.4 },
  source_updated_at: { floor: TIMESTAMP_COLUMN_FLOOR, share: 1 },
}

// The four labels name one axis - which registry reported the product - and
// each is the subject term its own law uses: 식품 (식품위생법), 축산물 (축산물
// 위생관리법), 건강기능식품 (건강기능식품법), 수입식품 (수입식품안전관리 특별법).
// No invented modifier, so nothing here has to be spelled twice: an imported
// supplement is 수입식품 because that is the law it is registered under. Widest
// rendered badge is the English 'Health functional food', 204px with the
// badge's nowrap padding, which is what the column's floor is cut for.
// One colour per registry, so the four kinds are told apart at a glance and a
// new kind is a line here rather than a ternary that silently lumps it in.
const KIND_COLOUR = {
  domestic: 'info',
  livestock: 'warning',
  import: 'success',
  health_functional: 'secondary',
} as const

/** The grid props a column's floor and share become. */
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})

/**
 * Columns a reader opens on purpose; the grid's selector brings them back.
 * What every kind answers stands in front - 품목번호, 제품명, 식품유형, 보고 업소,
 * 제조업소, 제조국, 보고일자 - and what only one registry publishes starts hidden:
 * the eleven 품목제조보고 fields are NULL on 860,735 of 1,933,036 rows
 * (livestock + import, 2026-09-14), and 영문 제품명 on the other 1,640,212.
 */
const HIDDEN_BY_DEFAULT: Record<string, boolean> = {
  product_name_en: false,
  license_no: false,
  industry_name: false,
  shelf_life: false,
  product_form: false,
  packaging_material: false,
  usage_method: false,
  purpose: false,
  quality_maintenance_days: false,
  production_ended: false,
  high_calorie_low_nutrition: false,
  child_favorite_certified_yn: false,
  domestic_export_type: false,
}

/**
 * The columns this screen filters, in the order the boxes stand - the query
 * parameters' names, so a box and the parameter it sends cannot drift apart.
 * Two are closed vocabularies and get selects; the rest are free text.
 */
const FILTER_FIELDS = [
  'report_kind',
  'item_report_no',
  'product_name',
  'business_name',
  'license_no',
  'product_type_name',
] as const

/**
 * The two closed vocabularies, from two different places. The kind is the
 * schema's own `Literal`, so its options are the contract's constant - the pair
 * cannot change overnight, and nothing is fetched for it. The 식품유형 is a
 * column's values (814 of them, measured 2026-09-10), so it is a facets read:
 * the 공전 gains a type and the sync brings it the night it appears.
 */
const SELECT_FIELDS = ['report_kind', 'product_type_name'] as const

/** The one select whose options are codes, not the rows' own words. */
const CODE_FIELD = 'report_kind'

const FILTER_LABEL_KEYS = {
  report_kind: 'item_report.filter.kind',
  item_report_no: 'item_report.filter.number',
  product_name: 'item_report.filter.product',
  business_name: 'item_report.filter.business',
  license_no: 'item_report.filter.license',
  product_type_name: 'item_report.filter.type',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

type SelectField = (typeof SELECT_FIELDS)[number]

export default function FoodItemReportDerivedList() {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  const grid = useDataGridState()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<FoodItemReportListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useFoodItemReportList(params)
  const facets = useFoodItemReportFacets()
  const [openId, setOpenId] = useState<string | null>(null)

  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(facets, tCommon('messages.load_failed'))

  const { setColumnVisibilityModel } = grid
  useEffect(() => {
    setColumnVisibilityModel((current) => ({ ...HIDDEN_BY_DEFAULT, ...current }))
  }, [setColumnVisibilityModel])

  const columns = useMemo<GridColDef<FoodItemReport>[]>(
    () => [
      {
        ...sized('report_kind'),
        headerName: t('item_report.table.kind'),
        renderCell: ({ row }) => (
          <Label variant="soft" color={KIND_COLOUR[row.report_kind]}>
            {t(`item_report.kind.${row.report_kind}`)}
          </Label>
        ),
      },
      { ...sized('item_report_no'), headerName: t('item_report.table.number') },
      { ...sized('product_name'), headerName: t('item_report.table.product') },
      { ...sized('product_type_name'), headerName: t('item_report.table.type') },
      { ...sized('business_name'), headerName: t('item_report.table.business') },
      { ...sized('maker_name'), headerName: t('item_report.table.maker') },
      { ...sized('origin_country'), headerName: t('item_report.table.origin') },
      { ...sized('product_name_en'), headerName: t('item_report.table.product_en') },
      {
        ...sized('report_date'),
        headerName: t('item_report.table.report_date'),
        // The registry writes `20260915` and the ledger keeps it verbatim; a
        // reader should not have to count characters.
        valueFormatter: (value: string) => formatPortalDate(value),
      },
      { ...sized('license_no'), headerName: t('item_report.table.license') },
      { ...sized('industry_name'), headerName: t('item_report.table.industry') },
      { ...sized('shelf_life'), headerName: t('item_report.table.shelf_life') },
      { ...sized('product_form'), headerName: t('item_report.table.product_form') },
      { ...sized('packaging_material'), headerName: t('item_report.table.packaging') },
      { ...sized('usage_method'), headerName: t('item_report.table.usage') },
      { ...sized('purpose'), headerName: t('item_report.table.purpose') },
      {
        ...sized('quality_maintenance_days'),
        headerName: t('item_report.table.quality_days'),
      },
      { ...sized('production_ended'), headerName: t('item_report.table.production_ended') },
      {
        ...sized('high_calorie_low_nutrition'),
        headerName: t('item_report.table.high_calorie'),
      },
      {
        ...sized('child_favorite_certified_yn'),
        headerName: t('item_report.table.child_favorite'),
      },
      { ...sized('domestic_export_type'), headerName: t('item_report.table.export') },
      {
        ...sized('source_updated_at'),
        headerName: t('item_report.table.source_updated_at'),
        renderCell: ({ value }) => (value === null ? '—' : formatDateTime(String(value))),
      },
    ],
    [t],
  )

  return (
    <Card>
      <ListCardHead
        title={t('item_report.list_title')}
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
              // A select while its options are loading is a select with one entry,
              // "all" - it never falls back to a text box, which would send a
              // contains-match the router answers with equals.
              options: !SELECT_FIELDS.includes(field as SelectField)
                ? undefined
                : field === CODE_FIELD
                  ? REPORT_KINDS
                  : (facets.data?.product_type_name ?? []),
              // The kind is a code the schema closes, not a word: it reads through
              // the locale. A type name is the row's own text and reads as itself.
              optionLabel:
                field === CODE_FIELD
                  ? (value) => t(`item_report.kind.${value as ReportKind}`)
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

      <FoodItemReportDetailDialog
        open={openId !== null}
        onClose={() => setOpenId(null)}
        itemReportId={openId}
      />
    </Card>
  )
}
