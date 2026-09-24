/**
 * One item report - domestic, livestock or imported - read inside one dialog.
 *
 * The record dialog shape with its write half removed: a header that says what
 * the record is, a tab strip, and tabs that present what they were handed. No
 * panel replaces the body, because nothing here is edited - the report and its
 * three edges are rebuilt off the ledgers every night, and a change made here
 * would be gone by morning.
 *
 * The dialog owns what has the dialog's lifetime: which tab shows and where
 * each edge's table is paged to. Paging cannot live in the tab - switching tabs
 * unmounts it - and the close transition resets both, so the next row opens
 * on the first tab, page one.
 */

import { useState } from 'react'
import {
  Box,
  CircularProgress,
  Dialog,
  DialogContent,
  Grid,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import DetailField from '@/components/detail/DetailField'
import DetailSection from '@/components/detail/DetailSection'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'
import Label from '@/components/label/Label'
import { RECORD_SURFACE } from '@/config'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useServerTablePage } from '@/hooks/useServerTablePage'
import { useTablePage } from '@/hooks/useTablePage'
import {
  useFoodItemReport,
  useFoodItemReportDeclarations,
  useFoodItemReportSafetyRecords,
  useFoodItemReportLabels,
  useFoodItemReportStandards,
} from '@/lib/api/hooks/useFood'
import FoodItemReportDeclarationsTab from '@/sections/food/detail/FoodItemReportDeclarationsTab'
import FoodSafetyRecordsTab from '@/sections/food/detail/FoodSafetyRecordsTab'
import FoodItemReportIngredientsTab from '@/sections/food/detail/FoodItemReportIngredientsTab'
import FoodItemReportLabelTab from '@/sections/food/detail/FoodItemReportLabelTab'
import FoodItemReportNutritionTab from '@/sections/food/detail/FoodItemReportNutritionTab'
import FoodItemReportStandardsTab from '@/sections/food/detail/FoodItemReportStandardsTab'
import { formatDateTime, formatPortalDate } from '@/utils/formatTime'
import type {
  FoodItemReportDeclaration,
  FoodItemReportDetail,
  FoodSafetyRecord,
  FoodItemReportIngredient,
  FoodItemReportLabel,
  FoodItemReportTypeStandards,
} from '@/types/food'

type DetailTab = 'record' | 'ingredients' | 'standards' | 'history'

const TAB_ICONS: Record<DetailTab, ActionIcon> = {
  record: 'info',
  ingredients: 'layers',
  standards: 'shield',
  history: 'clock',
}

/**
 * 제품 정보 → 원재료 → 기준규격 → 이력.
 *
 * A tab is what a reader pages through. 표시사항 and 영양성분 are one row per
 * product (299,273 and 172,352 of 1,978,865, measured 2026-09-16), so they are
 * cards of 제품 정보 - drawn for every product, and saying so when the registry
 * published none. A missing card and a card that says "none" are different
 * facts, and only the second is true here.
 */
const TAB_ORDER: DetailTab[] = ['record', 'ingredients', 'standards', 'history']

/** The dialog body's floor lives with the other record-surface metrics. */
const BODY_MIN_HEIGHT = RECORD_SURFACE.BODY_MIN_HEIGHT

/**
 * Stable identities: paging memoises on the row array, and `[]` written inline
 * would be a new array on every render while the report is still loading.
 */
const EMPTY_INGREDIENTS: FoodItemReportIngredient[] = []
const EMPTY_TYPES: FoodItemReportTypeStandards[] = []
const EMPTY_LABELS: FoodItemReportLabel[] = []

/**
 * Every column of the record, in one card, in reading order: what it is, who
 * reported and made it, when, and what the registry says the package is like.
 *
 * One list for all four registries - a column means one thing here, and a row
 * leaves NULL what its registry does not publish. **Every field is drawn**, with
 * an em dash where the answer is NULL: measured 2026-09-16, an import product
 * answers none of 인허가번호, 업종, 소비기한 or 성상 (0 %) against a domestic
 * one's 100/100/96/98 %, and skipping them read as "this screen has no such
 * field" rather than "this registry publishes none". Four headings were four
 * scroll stops for the same reason, so they are one card.
 */
/**
 * The fields whose value is a portal code, and the key its words live under.
 *
 * `ETQTY_XPORT_PRDLST_YN` is 내수/겸용구분 - `N` is 내수 전용 and `O` is
 * 수출 겸용, as the operation's own field description states. There is no
 * "export only" value. Printing the letter made the reader guess, and the old
 * label ("내수/수출") named a distinction the registry does not draw. Measured
 * 2026-09-16 over the 1,072,302 domestic reports: O 592,328 · N 417,281 ·
 * none 62,693; the other three registries publish the column not at all.
 */
const CODED_FIELDS: Partial<Record<(typeof RECORD_FIELDS)[number], string>> = {
  domestic_export_type: 'item_report.domestic_export',
}

const RECORD_FIELDS = [
  'item_report_no',
  'product_name',
  'product_name_en',
  'product_type_name',
  'business_name',
  'maker_name',
  'origin_country',
  'license_no',
  'industry_name',
  'report_date',
  'shelf_life',
  'quality_maintenance_days',
  'production_ended',
  'primary_functionality',
  'functional_indicator',
  'intake_caution',
  'storage_method',
  'standard_spec',
  'product_form',
  'packaging_material',
  'usage_method',
  'high_calorie_low_nutrition',
  'child_favorite_certified_yn',
  'domestic_export_type',
] as const

interface FoodItemReportDetailDialogProps {
  open: boolean
  onClose: () => void
  itemReportId: string | null
}

// One colour per registry, so the three kinds are told apart at a glance and a
// new kind is a line here rather than a ternary that silently lumps it in.
const KIND_COLOUR = {
  domestic: 'info',
  livestock: 'warning',
  import: 'success',
  health_functional: 'secondary',
} as const

export default function FoodItemReportDetailDialog({
  open,
  onClose,
  itemReportId,
}: FoodItemReportDetailDialogProps) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')
  const [tab, setTab] = useState<DetailTab>('record')
  const query = useFoodItemReport(open ? itemReportId : null)
  const report = query.data

  const ingredientPaging = useTablePage(report?.ingredients ?? EMPTY_INGREDIENTS)

  /**
   * The events are read with the 제품 정보 tab, where the section that draws
   * them stands: an authority's action is something a reader meets while
   * looking at the product, and the list of every event is its own screen.
   * Server-paged, one window at a time, and only fetched where it is shown.
   */
  const eventPage = useServerTablePage<FoodSafetyRecord>()
  const eventsQuery = useFoodItemReportSafetyRecords(
    open && tab === 'record' ? itemReportId : null,
    eventPage.params,
  )
  const events = eventPage.resolve(eventsQuery.data)

  const declarationPage = useServerTablePage<FoodItemReportDeclaration>()
  const declarationsQuery = useFoodItemReportDeclarations(
    open && tab === 'history' ? itemReportId : null,
    declarationPage.params,
  )
  const declarations = declarationPage.resolve(declarationsQuery.data)

  /**
   * The standards are read when their tab opens, not with the report: the walk
   * up two trees is the one read here that costs more than a row. An outline,
   * not a table, so nothing of it pages.
   */
  /**
   * The labels are read when their tab opens: most reports have none - the two
   * portals together cover 9,750 of the 1,640,212 reports (2026-09-13) - so the
   * read is not worth making with the row.
   */
  const labelsQuery = useFoodItemReportLabels(open && tab === 'record' ? itemReportId : null)
  const labels = labelsQuery.data?.labels ?? EMPTY_LABELS

  const standardsQuery = useFoodItemReportStandards(
    open && tab === 'standards' ? itemReportId : null,
  )
  const types = standardsQuery.data?.types ?? EMPTY_TYPES

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(labelsQuery, tCommon('messages.load_failed'))
  useQueryErrorToast(declarationsQuery, tCommon('messages.load_failed'))
  useQueryErrorToast(eventsQuery, tCommon('messages.load_failed'))
  useQueryErrorToast(standardsQuery, tCommon('messages.load_failed'))

  /** Reset once the close transition has finished, so the body does not snap while fading out. */
  const resetBody = () => {
    setTab('record')
    ingredientPaging.reset()
    declarationPage.reset()
    eventPage.reset()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={RECORD_SURFACE.DIALOG_MAX_WIDTH}
      fullWidth
      slotProps={{ transition: { onExited: resetBody } }}
    >
      <Stack direction="row" alignItems="flex-start" sx={{ p: 3, pb: 2 }}>
        <Stack spacing={1} sx={{ flexGrow: 1 }}>
          <Box>
            <Typography variant="h6">
              {report?.product_name ?? t('item_report.record_title')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {report?.item_report_no ?? ''}
            </Typography>
          </Box>

          {report !== undefined && (
            <>
              <Stack direction="row" spacing={1}>
                <Label variant="soft" color={KIND_COLOUR[report.report_kind]}>
                  {t(`item_report.kind.${report.report_kind}`)}
                </Label>
                {report.product_type_name !== null && (
                  <Label variant="soft" color="default">
                    {report.product_type_name}
                  </Label>
                )}
              </Stack>

            </>
          )}
        </Stack>

        <IconButton onClick={onClose} size="small">
          <Iconify name="close" />
        </IconButton>
      </Stack>

      <Tabs
        value={tab}
        onChange={(_event, value: DetailTab) => setTab(value)}
        sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}
      >
        {TAB_ORDER.map((name) => (
          <Tab
            key={name}
            value={name}
            label={name === 'history' ? t(historyTabKey(report)) : t(`item_report.tabs.${name}`)}
            icon={<Iconify name={TAB_ICONS[name]} />}
          />
        ))}
      </Tabs>

      <DialogContent sx={{ minHeight: BODY_MIN_HEIGHT, bgcolor: 'background.neutral', p: 3 }}>
        {/* One gap between cards, whatever the tab draws: measured 2026-09-16,
            the record tab stacked its cards at 0px while the standards tab
            stood at 24px and two other tabs at 16px. */}
        <Stack spacing={RECORD_SURFACE.SECTION_GAP}>
          {query.isLoading && (
            <Stack alignItems="center" sx={{ py: 6 }}>
              <CircularProgress />
            </Stack>
          )}

          {report !== undefined && tab === 'record' && report.record_count > 0 && (
            <FoodSafetyRecordsTab
              rows={events.rows}
              pagination={events.pagination}
              loading={eventsQuery.isFetching}
              failedCount={report.failed_record_count > 0 ? report.failed_record_count : null}
              lastRecordedOn={report.last_recorded_on}
            />
          )}

          {report !== undefined && tab === 'record' && report.record_count === 0 && (
            <DetailSection name="shield" title={t('item_report.event.section')}>
              <Typography variant="body2" color="text.secondary">
                {t('item_report.event.empty')}
              </Typography>
            </DetailSection>
          )}

          {report !== undefined && tab === 'record' && (
            <DetailSection name="info" title={t('item_report.tabs.record')}>
              <Grid container spacing={2}>
                {RECORD_FIELDS.map((field) => (
                  <Grid key={field} size={{ xs: 12, sm: 6 }}>
                    <DetailField label={t(`item_report.field.${field}`)}>
                      {coded(t, field, report[field])}
                    </DetailField>
                  </Grid>
                ))}
              </Grid>
            </DetailSection>
          )}

          {report !== undefined && tab === 'record' && (
            <FoodItemReportLabelTab labels={labels} />
          )}

          {report !== undefined && tab === 'record' && (
            <FoodItemReportNutritionTab
              nutritions={report.nutritions}
              reportKind={report.report_kind}
            />
          )}

          {report !== undefined && tab === 'record' && (
            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
              {t('item_report.detail_audit', {
                at:
                  report.source_updated_at === null
                    ? '—'
                    : formatDateTime(report.source_updated_at),
                derived: formatDateTime(report.updated_at),
              })}
            </Typography>
          )}

          {report !== undefined && tab === 'history' && report.declaration_count === 0 && (
            <DetailSection name="clock" title={t(historyTabKey(report))}>
              <Typography variant="body2" color="text.secondary">
                {t('item_report.history.empty')}
              </Typography>
            </DetailSection>
          )}
          {report !== undefined && tab === 'history' && report.declaration_count > 0 && (
            <FoodItemReportDeclarationsTab
              reportKind={report.report_kind}
              rows={declarations.rows}
              pagination={declarations.pagination}
              loading={declarationsQuery.isFetching}
            />
          )}
          {report !== undefined && tab === 'ingredients' && (
            <FoodItemReportIngredientsTab paging={ingredientPaging} />
          )}
          {report !== undefined && tab === 'standards' && standardsQuery.isLoading && (
            <Stack alignItems="center" sx={{ py: 6 }}>
              <CircularProgress />
            </Stack>
          )}
          {report !== undefined && tab === 'standards' && standardsQuery.data !== undefined && (
            <FoodItemReportStandardsTab types={types} />
          )}
        </Stack>
      </DialogContent>
    </Dialog>
  )
}

/**
 * One field as a reader reads it.
 *
 * A registry that answered nothing is drawn as an em dash rather than left out:
 * measured 2026-09-16, an import product answers none of 인허가번호, 업종,
 * 소비기한 or 성상 (0 %) against a domestic one's 100/100/96/98 %, and skipping
 * them made a card vanish - which reads as "this screen has no such field",
 * not as "this registry publishes none". The two are different facts.
 */
function displayed(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  return formatPortalDate(String(value))
}

/**
 * One field's value, read through the registry's own vocabulary when it has one.
 *
 * A code is the registry's shorthand, not the reader's: `O` means 수출 겸용 and
 * says so only in the operation's field description. A field the table above
 * does not name is read as it stands.
 */
function coded(
  translate: TFunction<'food'>,
  field: (typeof RECORD_FIELDS)[number],
  value: unknown,
): string {
  const vocabulary = CODED_FIELDS[field]
  if (vocabulary === undefined || value === null || value === undefined) return displayed(value)
  return translate(`${vocabulary}.${String(value)}`, { defaultValue: String(value) })
}

/**
 * What the history tab is called for this product - the registry decides.
 *
 * A 수입식품 declares crossings (수입신고), every other registry declares a
 * year's figures (생산실적); no product carries both (measured 2026-09-20). One
 * word for both read as neither, and the section beneath it was headed
 * "수입신고 이력" on a domestic product, which publishes no such thing.
 * Falls back while the report is still loading, when there is no kind to ask.
 */
function historyTabKey(
  report: FoodItemReportDetail | undefined,
): 'item_report.tabs.history' | 'item_report.tabs.declaration' | 'item_report.tabs.production' {
  if (report === undefined) return 'item_report.tabs.history'
  return report.report_kind === 'import'
    ? 'item_report.tabs.declaration'
    : 'item_report.tabs.production'
}
