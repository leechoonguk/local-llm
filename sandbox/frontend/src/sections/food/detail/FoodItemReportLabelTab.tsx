/**
 * What the packages say: every printed label of this report, from either portal.
 *
 * A tab is a pure presenter - it takes the labels it was handed and queries
 * nothing. One card per label: its printed fields, the allergens it declares,
 * the 주의사항 it prints and the packaging parts it names. Nothing pages: a label
 * carries 11 allergens at the widest and 8 caution sentences (measured
 * 2026-09-13), which is a card, not a table.
 *
 * The two portals are never merged into one card. Measured 2026-09-13 on the 56
 * 품목보고번호 both publish: 제품명 agrees on 34 and 내용량 on 11, because one
 * report covers several packages and each portal holds different ones. The
 * source is a badge on the card, so a reader knows which package is being read.
 *
 * An allergen is shown once per label: a package declares the same substance
 * once per 표시그룹 - a sandwich lists 우유 for its bread, its sauce and its
 * filling - and the derivation already keeps one row per name.
 *
 * An allergen section says one of three things, never two: the substances the
 * label declares, 없음 where the publisher wrote it, or "the publisher did not
 * say" - 8,479 of the HACCP feed's 14,664 rows read 알수없음, and 새우탕큰사발면
 * declares twelve substances on its 푸드QR label against 알수없음 on its HACCP
 * one. Rendering the third as the second would call that package allergen-free.
 *
 * Only the Food QR portal publishes cautions, packaging parts and the Y/N
 * declarations; a HACCP card shows the fields it has and says nothing about the
 * rest, rather than showing an empty section for each.
 */

import { Grid, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailField from '@/components/detail/DetailField'
import { RECORD_SURFACE } from '@/config'
import DetailSection from '@/components/detail/DetailSection'
import Label from '@/components/label/Label'
import {
  ALLERGEN_DECLARED,
  ALLERGEN_NONE,
  FOOD_QR_LABEL_SOURCE,
  LABEL_FIELDS,
  LABEL_FLAGS,
} from '@/types/food'
import type { FoodItemReportLabel, LabelSource } from '@/types/food'

// One colour per registry that prints labels, so a fourth source is a line
// here rather than a ternary that silently draws it as HACCP.
const SOURCE_LABEL_KEYS = {
  'food-qr': 'item_report.label.source.food-qr',
  haccp: 'item_report.label.source.haccp',
  import: 'item_report.label.source.import',
} as const

const SOURCE_COLOUR: Record<LabelSource, 'info' | 'warning' | 'success'> = {
  'food-qr': 'info',
  haccp: 'warning',
  import: 'success',
}

export default function FoodItemReportLabelTab({ labels }: { labels: FoodItemReportLabel[] }) {
  const { t } = useTranslation('food')

  if (labels.length === 0) {
    return (
      <DetailSection name="info" title={t('item_report.tabs.label')}>
        <Typography variant="body2" color="text.secondary">
          {t('item_report.label.none')}
        </Typography>
      </DetailSection>
    )
  }

  return (
    <Stack spacing={RECORD_SURFACE.SECTION_GAP}>
      {labels.map((label) => (
        <DetailSection
          key={label.id}
          name="info"
          title={t('item_report.label.title', { label_key: label.label_key })}
        >
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Label variant="soft" color={SOURCE_COLOUR[label.source as LabelSource]}>
                {t(SOURCE_LABEL_KEYS[label.source as LabelSource])}
              </Label>
              <Typography variant="caption" color="text.secondary">
                {t('item_report.label.printed')}
              </Typography>
            </Stack>

            <Grid container spacing={2}>
              {LABEL_FIELDS.map((field) => (
                <Grid key={field} size={{ xs: 12, sm: 6 }}>
                  <DetailField label={t(`item_report.label.${field}`)}>
                    {label[field]}
                  </DetailField>
                </Grid>
              ))}
              {label.raw_material_text !== null && (
                <Grid size={{ xs: 12 }}>
                  <DetailField label={t('item_report.label.raw_material_text')}>
                    {label.raw_material_text}
                  </DetailField>
                </Grid>
              )}
              {label.functional_info_text !== null && (
                <Grid size={{ xs: 12 }}>
                  <DetailField label={t('item_report.label.functional_info_text')}>
                    {label.functional_info_text}
                  </DetailField>
                </Grid>
              )}
            </Grid>

            <Stack spacing={1}>
              <Typography variant="subtitle2">{t('item_report.label.allergens')}</Typography>
              {label.allergen_declaration !== ALLERGEN_DECLARED ? (
                <Typography
                  variant="body2"
                  color={
                    label.allergen_declaration === ALLERGEN_NONE ? 'text.secondary' : 'warning.dark'
                  }
                >
                  {label.allergen_declaration === ALLERGEN_NONE
                    ? t('item_report.label.no_allergens')
                    : t('item_report.label.unknown_allergens')}
                </Typography>
              ) : (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {label.allergens.map((allergen) => (
                    <Label key={allergen.id} variant="soft" color="warning">
                      {allergen.name ?? '—'}
                    </Label>
                  ))}
                </Stack>
              )}
            </Stack>

            {label.cautions.length > 0 && (
              <Stack spacing={1}>
                <Typography variant="subtitle2">{t('item_report.label.cautions')}</Typography>
                {label.cautions.map((caution) => (
                  <Typography key={caution.id} variant="body2" color="text.secondary">
                    {caution.caution_text}
                  </Typography>
                ))}
              </Stack>
            )}

            {label.packagings.length > 0 && (
              <Stack spacing={1}>
                <Typography variant="subtitle2">{t('item_report.label.packagings')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {label.packagings.map((part) => (
                    <Label key={part.id} variant="soft" color="default">
                      {part.packaging_text ?? '—'}
                    </Label>
                  ))}
                </Stack>
              </Stack>
            )}

            {label.source === FOOD_QR_LABEL_SOURCE && (
              <Stack spacing={1}>
                <Typography variant="subtitle2">{t('item_report.label.flags')}</Typography>
                <Grid container spacing={2}>
                  {LABEL_FLAGS.map((flag) => (
                    <Grid key={flag} size={{ xs: 6, sm: 3 }}>
                      <DetailField label={t(`item_report.label.${flag}`)}>
                        {label[flag] === null
                          ? null
                          : label[flag] === 'Y'
                            ? t('item_report.label.yes')
                            : t('item_report.label.no')}
                      </DetailField>
                    </Grid>
                  ))}
                </Grid>
              </Stack>
            )}
          </Stack>
        </DetailSection>
      ))}

    </Stack>
  )
}
