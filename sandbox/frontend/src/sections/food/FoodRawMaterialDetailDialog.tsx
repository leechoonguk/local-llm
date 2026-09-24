/**
 * One raw material, read and never edited - the 품목제조보고 dialog's shape.
 *
 * The dialog owns the query and the paging; the tabs are pure presenters.
 * Two tabs: the record (the synonym lists the grid could not hold, the
 * composition's part, process and state), and the base's variants - every
 * code the same base material is written under, this one included.
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
import DetailField from '@/components/detail/DetailField'
import DetailSection from '@/components/detail/DetailSection'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'
import Label from '@/components/label/Label'
import { RECORD_SURFACE } from '@/config'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useServerTablePage } from '@/hooks/useServerTablePage'
import { useTablePage } from '@/hooks/useTablePage'
import { useFoodRawMaterial, useFoodRawMaterialItemReports } from '@/lib/api/hooks/useFood'
import FoodRawMaterialItemReportsTab from '@/sections/food/detail/FoodRawMaterialItemReportsTab'
import FoodRawMaterialVariantsTab from '@/sections/food/detail/FoodRawMaterialVariantsTab'
import { formatDateTime } from '@/utils/formatTime'
import type { FoodItemReport, FoodRawMaterial } from '@/types/food'

type DetailTab = 'record' | 'variants' | 'products'

const TAB_ICONS: Record<DetailTab, ActionIcon> = {
  record: 'info',
  variants: 'layers',
  products: 'link',
}

const TAB_ORDER: DetailTab[] = ['record', 'variants', 'products']

/** The dialog body's floor lives with the other record-surface metrics. */
const BODY_MIN_HEIGHT = RECORD_SURFACE.BODY_MIN_HEIGHT

/**
 * Stable identity: paging memoises on the row array, and `[]` written inline
 * would be a new array on every render while the material is still loading.
 */
const EMPTY_VARIANTS: FoodRawMaterial[] = []

/** The registry's own columns the grid does not carry, in the order the record tab lists them. */
const RECORD_FIELDS = [
  'base_code',
  'raw_material_status_code_name',
  'region_code_name',
  'process_code_name',
  'raw_material_alias',
  'english_name',
  'scientific_name',
] as const

interface FoodRawMaterialDetailDialogProps {
  open: boolean
  onClose: () => void
  rawMaterialId: string | null
}

export default function FoodRawMaterialDetailDialog({
  open,
  onClose,
  rawMaterialId,
}: FoodRawMaterialDetailDialogProps) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')
  const [tab, setTab] = useState<DetailTab>('record')
  const query = useFoodRawMaterial(open ? rawMaterialId : null)
  const material = query.data

  const variantPaging = useTablePage(material?.variants ?? EMPTY_VARIANTS)

  /**
   * The products are read when their tab opens, not with the material: the
   * edge is ten million ingredient rows deep, and a flour is named by 94,342
   * labels. Server-paged, one window at a time.
   */
  const productPage = useServerTablePage<FoodItemReport>()
  const productsQuery = useFoodRawMaterialItemReports(
    open && tab === 'products' ? rawMaterialId : null,
    productPage.params,
  )
  const products = productPage.resolve(productsQuery.data)

  useQueryErrorToast(query, tCommon('messages.load_failed'))
  useQueryErrorToast(productsQuery, tCommon('messages.load_failed'))

  /** Reset once the close transition has finished, so the body does not snap while fading out. */
  const resetBody = () => {
    setTab('record')
    variantPaging.reset()
    productPage.reset()
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
              {material?.representative_raw_material_name ?? t('raw_material.record_title')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {material?.raw_material_code ?? ''}
            </Typography>
          </Box>

          {material !== undefined && (
            <>
              <Stack direction="row" spacing={1}>
                {material.use_yn !== null && (
                  <Label variant="soft" color={material.use_yn === 'Y' ? 'success' : 'default'}>
                    {material.use_yn === 'Y' ? t('raw_material.use.Y') : t('raw_material.use.N')}
                  </Label>
                )}
                {material.raw_material_large_class !== null && (
                  <Label variant="soft" color="info">
                    {material.raw_material_large_class}
                  </Label>
                )}
                {material.raw_material_medium_class !== null && (
                  <Label variant="soft" color="default">
                    {material.raw_material_medium_class}
                  </Label>
                )}
              </Stack>

              <Typography variant="caption" color="text.secondary">
                {t('raw_material.detail_audit', {
                  at:
                    material.source_updated_at === null
                      ? '—'
                      : formatDateTime(material.source_updated_at),
                  derived: formatDateTime(material.updated_at),
                })}
              </Typography>
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
            label={t(`raw_material.tabs.${name}`)}
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

          {material !== undefined && tab === 'record' && (
            <DetailSection name="info" title={t('raw_material.tabs.record')}>
              <Grid container spacing={2}>
                {RECORD_FIELDS.map((field) => (
                  <Grid key={field} size={{ xs: 12, sm: 6 }}>
                    <DetailField label={t(`raw_material.field.${field}`)}>
                      {material[field]}
                    </DetailField>
                  </Grid>
                ))}
              </Grid>
            </DetailSection>
          )}
          {material !== undefined && tab === 'variants' && (
            <FoodRawMaterialVariantsTab paging={variantPaging} />
          )}
          {material !== undefined && tab === 'products' && productsQuery.isLoading && (
            <Stack alignItems="center" sx={{ py: 6 }}>
              <CircularProgress />
            </Stack>
          )}
          {material !== undefined && tab === 'products' && productsQuery.data !== undefined && (
            <FoodRawMaterialItemReportsTab
              rows={products.rows}
              pagination={products.pagination}
              loading={productsQuery.isFetching}
            />
          )}
        </Stack>
      </DialogContent>
    </Dialog>
  )
}
