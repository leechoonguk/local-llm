/**
 * The 위해정보 list - what authorities published about products, across every registry.
 *
 * Its own screen, and the reason is what the rows are: a 회수 공고 or a 검사
 * 부적합 is not the owner's declaration but an authority's action, and such a
 * thing is read by date and kind over everything rather than one product at a
 * time. 946 events stand against 1.9M products (2026-09-14), so as a column on
 * the product list it was a number that is zero on 99.95% of rows.
 *
 * The **derived list** shape, like the report list: paging and columns from
 * `useDataGridState`, the page from `useFoodSafetyRecordList`, one box per
 * filterable column from `useListFilters`, and no write half - the derive job
 * rebuilds these rows every night.
 *
 * A row opens the product it names; an event whose 품목제조보고번호 matches no
 * product opens nothing, because there is nothing to open - the registries
 * publish events for numbers they no longer carry, and the row's own columns
 * (제품명, 업소명, 사유) are what that event says.
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@mui/material'
import type { GridColDef } from '@mui/x-data-grid'
import ListCardHead from '@/components/data-grid/ListCardHead'
import ListFilters from '@/components/data-grid/ListFilters'
import ServerDataGrid from '@/components/data-grid/ServerDataGrid'
import Label from '@/components/label/Label'
import { formatPortalDate } from '@/utils/formatTime'
import { useDataGridState } from '@/hooks/useDataGridState'
import { useListFilters } from '@/hooks/useListFilters'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useFoodItemReportByKey, useFoodSafetyRecordFacets, useFoodSafetyRecordList } from '@/lib/api/hooks/useFood'
import FoodItemReportDetailDialog from '@/sections/food/FoodItemReportDetailDialog'
import { JUDGMENT_CODES, REPORT_KINDS } from '@/types/food'
import type {
  FoodSafetyRecord,
  JudgmentCode,
  FoodSafetyRecordListParams,
  ReportKind,
} from '@/types/food'

/** Every column's floor and share, as on the report list. */
const COLUMN: Record<string, { floor: number; share: number }> = {
  recorded_on: { floor: 168, share: 0.6 },
  record_kind: { floor: 173, share: 0.6 },
  judgment_code: { floor: 140, share: 0.5 },
  report_kind: { floor: 204, share: 0.5 },
  item_report_no: { floor: 160, share: 1 },
  product_name: { floor: 200, share: 1.6 },
  business_name: { floor: 209, share: 1.2 },
  reason: { floor: 200, share: 1.6 },
  grade: { floor: 208, share: 0.4 },
  institution_name: { floor: 156, share: 0.8 },
}

/** One colour per kind of record, so a recall reads as one at a glance. */
const RECORD_COLOUR = {
  recall: 'error',
  inspection_failure: 'warning',
  collection_inspection: 'info',
} as const

/**
 * One colour per verdict. 부적합 is the reason anyone opens this screen, 적합 is
 * the answer for 68.3 % of the feed, and the other three say the verdict is not
 * settled - so they read as neither.
 */
const JUDGMENT_COLOUR: Record<JudgmentCode, 'error' | 'success' | 'default'> = {
  failed: 'error',
  passed: 'success',
  pending: 'default',
}

/** One colour per registry, the same vocabulary the report list uses. */
const KIND_COLOUR = {
  domestic: 'info',
  livestock: 'warning',
  import: 'success',
  health_functional: 'secondary',
} as const

// The order is the server's - newest first, which is how a list of things that
// happened is read - so every column says so and no header answers 422.
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
  sortable: false as const,
})

/**
 * The columns this screen filters, in the order the boxes stand. Three are
 * closed vocabularies the feeds publish from; the date bounds and the names
 * are typed.
 */
const FILTER_FIELDS = [
  'record_kind',
  'judgment_code',
  'report_kind',
  'record_year',
  'recorded_on_from',
  'recorded_on_to',
  'item_report_no',
  'product_name',
  'business_name',
] as const

const SELECT_FIELDS = ['record_kind', 'judgment_code', 'report_kind', 'record_year'] as const

/** The two selects whose options are codes rather than the rows' own words. */
const CODE_FIELDS = ['record_kind', 'judgment_code', 'report_kind'] as const

const FILTER_LABEL_KEYS = {
  record_kind: 'item_report.event.filter.kind',
  judgment_code: 'item_report.event.filter.judgment',
  report_kind: 'item_report.filter.kind',
  record_year: 'item_report.event.filter.year',
  recorded_on_from: 'item_report.event.filter.date_from',
  recorded_on_to: 'item_report.event.filter.date_to',
  item_report_no: 'item_report.filter.number',
  product_name: 'item_report.filter.product',
  business_name: 'item_report.filter.business',
} as const

type FilterField = (typeof FILTER_FIELDS)[number]

type SelectField = (typeof SELECT_FIELDS)[number]

export default function FoodSafetyRecordDerivedList() {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  const grid = useDataGridState()
  const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
  const params = useMemo<FoodSafetyRecordListParams>(
    () => ({ ...grid.params, ...filters.params }),
    [grid.params, filters.params],
  )
  const query = useFoodSafetyRecordList(params)
  const facets = useFoodSafetyRecordFacets()
  const [opened, setOpened] = useState<{ kind: ReportKind; number: string } | null>(null)

  const rows = query.data?.items ?? []
  const rowCount = query.data?.total ?? 0

  // The product an event names, looked up by the key the event carries. The
  // dialog opens on a row id, which only this read knows - so the row click
  // records the key and the dialog opens when *this* key's answer is in. The
  // read is keyed and disabled while nothing is open, because a lookup that
  // served the previous key's row opened the dialog on another product for two
  // frames (measured 2026-09-16).
  const product = useFoodItemReportByKey(
    opened === null ? null : { report_kind: opened.kind, item_report_no: opened.number },
  )
  const openedId = opened === null ? null : (product.data?.items[0]?.id ?? null)

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(facets, tCommon('messages.load_failed'))

  const columns = useMemo<GridColDef<FoodSafetyRecord>[]>(
    () => [
      {
        ...sized('recorded_on'),
        headerName: t('item_report.event.date'),
        sortable: false,
        // The authority publishes `20260915`; the ledger keeps that spelling and
        // the screen reads it as a date.
        valueFormatter: (value: string) => formatPortalDate(value),
      },
      {
        ...sized('record_kind'),
        headerName: t('item_report.event.kind_label'),
        sortable: false,
        renderCell: ({ row }) => (
          <Label variant="soft" color={RECORD_COLOUR[row.record_kind]}>
            {t(`item_report.event.kinds.${row.record_kind}`)}
          </Label>
        ),
      },
      {
        ...sized('judgment_code'),
        headerName: t('item_report.event.judgment'),
        sortable: false,
        // The normalised word, not the portal's: the filter beside this column
        // offers 적합 / 부적합 / 판정 전, and the portal writes four texts that
        // map onto three - 검토중 for pending, and 상기와같음 on 111,522 passed
        // rows, which tells a reader nothing. A filtered page whose badges spell
        // the filter differently reads like the filter missed. The registry's
        // own wording stays on the row and in the ledger.
        renderCell: ({ row }) =>
          row.judgment_code === null ? (
            '—'
          ) : (
            <Label variant="soft" color={JUDGMENT_COLOUR[row.judgment_code]}>
              {t(`item_report.event.judgments.${row.judgment_code}`)}
            </Label>
          ),
      },
      {
        ...sized('report_kind'),
        headerName: t('item_report.table.kind'),
        sortable: false,
        renderCell: ({ row }) =>
          row.report_kind === null ? (
            '—'
          ) : (
            <Label variant="soft" color={KIND_COLOUR[row.report_kind]}>
              {t(`item_report.kind.${row.report_kind}`)}
            </Label>
          ),
      },
      { ...sized('item_report_no'), headerName: t('item_report.table.number'), sortable: false },
      { ...sized('product_name'), headerName: t('item_report.table.product'), sortable: false },
      { ...sized('business_name'), headerName: t('item_report.table.business'), sortable: false },
      { ...sized('reason'), headerName: t('item_report.event.reason_or_item'), sortable: false },
      { ...sized('grade'), headerName: t('item_report.event.grade'), sortable: false },
      { ...sized('institution_name'), headerName: t('item_report.event.institution'), sortable: false },
    ],
    [t],
  )

  return (
    <Card>
      <ListCardHead
        title={t('item_report.event.list_title')}
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
                : field === 'report_kind'
                  ? REPORT_KINDS
                  : field === 'record_kind'
                    ? (facets.data?.record_kind ?? [])
                    : field === 'judgment_code'
                      ? JUDGMENT_CODES
                      : (facets.data?.record_year ?? []),
              optionLabel: !CODE_FIELDS.includes(field as (typeof CODE_FIELDS)[number])
                ? undefined
                : field === 'report_kind'
                  ? (value) => t(`item_report.kind.${value as ReportKind}`)
                  : field === 'judgment_code'
                    ? (value) => t(`item_report.event.judgments.${value as JudgmentCode}`)
                    : (value) =>
                        t(`item_report.event.kinds.${value as FoodSafetyRecord['record_kind']}`),
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
        onRowClick={(row) => {
          if (row.report_kind === null || row.item_report_no === null) return
          setOpened({ kind: row.report_kind, number: row.item_report_no })
        }}
      />

      <FoodItemReportDetailDialog
        open={openedId !== null}
        onClose={() => setOpened(null)}
        itemReportId={openedId}
      />
    </Card>
  )
}
