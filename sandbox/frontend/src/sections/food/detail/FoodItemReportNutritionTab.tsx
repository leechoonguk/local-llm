/**
 * The nutrition records that name this report - each drawn as the label's panel.
 *
 * Not a table: fifteen nutrients across a dialog's width clipped every header
 * to its first syllable (measured at 9 % a column), and a report has one record
 * for near enough all (57 of 172,419 have two), so each record is a section of
 * fields in the label's own order. An amount arrives at the column's scale
 * (`60.000000` for a portal `60`, six decimals being the ledger's, not the
 * label's), so the trailing zeros the storage added come off; nothing is
 * rounded, because a nutrient's precision is the portal's.
 */

import { Grid, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailField from '@/components/detail/DetailField'
import { RECORD_SURFACE } from '@/config'
import DetailSection from '@/components/detail/DetailSection'
import { LABEL_NUTRIENTS } from '@/types/food'
import type { FoodItemReportNutrition, ReportKind } from '@/types/food'

/** The kind the nutrition database does not key: it names domestic report numbers only. */
const IMPORT_REPORT_KIND = 'import'

/** `60.000000` → `60`, `0.250000` → `0.25`; a value with no zeros to shed is returned as is. */
const trimScale = (amount: string | null) =>
  amount === null ? null : amount.includes('.') ? amount.replace(/0+$/, '').replace(/\.$/, '') : amount

export default function FoodItemReportNutritionTab({
  nutritions,
  reportKind,
}: {
  nutritions: FoodItemReportNutrition[]
  /** Which registry reported it - the nutrition feed keys only the two domestic ones. */
  reportKind: ReportKind
}) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')

  if (nutritions.length === 0) {
    return (
      <DetailSection name="shield" title={t('item_report.tabs.nutrition')}>
        <Typography variant="body2" color="text.secondary">
          {reportKind === IMPORT_REPORT_KIND
            ? t('item_report.nutrition.not_for_import')
            : tCommon('messages.no_data')}
        </Typography>
      </DetailSection>
    )
  }

  return (
    <Stack spacing={RECORD_SURFACE.SECTION_GAP}>
      {nutritions.map((nutrition) => (
        <DetailSection
          key={nutrition.food_code}
          name="shield"
          title={`${nutrition.food_name ?? nutrition.food_code} · ${t('item_report.nutrition.basis')} ${nutrition.nutrient_basis_amount ?? '—'}`}
        >
          <Grid container spacing={2}>
            {LABEL_NUTRIENTS.map((key) => (
              <Grid key={key} size={{ xs: 6, sm: 4, md: 3 }}>
                <DetailField label={t(`item_report.nutrition.${key}`)}>
                  {trimScale(nutrition[key])}
                </DetailField>
              </Grid>
            ))}
            <Grid size={{ xs: 12 }}>
              <DetailField label={t('item_report.nutrition.source')}>{nutrition.source_name}</DetailField>
            </Grid>
          </Grid>
        </DetailSection>
      ))}
    </Stack>
  )
}
