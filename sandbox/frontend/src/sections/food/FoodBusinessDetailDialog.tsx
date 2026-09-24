/**
 * One licensed business, read and never edited - the 원재료 dialog's shape.
 *
 * The dialog owns the query and the paging; the tabs are pure presenters.
 * Three tabs: the record (the columns the grid does not carry), the rows under
 * the same name, and the licences on the same site. Neither list claims one
 * owner - nothing public keys a licence to a 법인등록번호 - so the record tab
 * carries that sentence rather than leaving the tables to imply otherwise.
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
import { useTablePage } from '@/hooks/useTablePage'
import { useFoodBusiness } from '@/lib/api/hooks/useFood'
import FoodBusinessRelatedTab from '@/sections/food/detail/FoodBusinessRelatedTab'
import { formatDateTime, formatPortalDate } from '@/utils/formatTime'
import type { FoodBusiness } from '@/types/food'

type DetailTab = 'record' | 'same_name' | 'same_site'

const TAB_ICONS: Record<DetailTab, ActionIcon> = {
  record: 'info',
  same_name: 'layers',
  same_site: 'link',
}

const TAB_ORDER: DetailTab[] = ['record', 'same_name', 'same_site']

/** The dialog body's floor lives with the other record-surface metrics. */
const BODY_MIN_HEIGHT = RECORD_SURFACE.BODY_MIN_HEIGHT

/**
 * Stable identity: paging memoises on the row array, and `[]` written inline
 * would be a new array on every render while the business is still loading.
 */
const EMPTY_RELATED: FoodBusiness[] = []

/** The registry's eight-digit dates, read as dates and never as digits. */
const DATE_FIELDS = ['permit_date', 'closed_date'] as const

/** A registry date, or nothing when the portal left it empty. */
const portalDate = (value: string | null) => (value === null ? null : formatPortalDate(value))

/** The columns the grid does not carry, in the order the record tab lists them. */
const RECORD_FIELDS = ['closure_kind', 'institution_name', 'site_key', 'name_key'] as const

interface FoodBusinessDetailDialogProps {
  open: boolean
  onClose: () => void
  businessId: string | null
}

export default function FoodBusinessDetailDialog({
  open,
  onClose,
  businessId,
}: FoodBusinessDetailDialogProps) {
  const { t } = useTranslation('food')
  const { t: tCommon } = useTranslation('common')
  const [tab, setTab] = useState<DetailTab>('record')
  const query = useFoodBusiness(open ? businessId : null)
  const business = query.data

  const namePaging = useTablePage(business?.same_name ?? EMPTY_RELATED)
  const sitePaging = useTablePage(business?.same_site ?? EMPTY_RELATED)

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  /** Reset once the close transition has finished, so the body does not snap while fading out. */
  const resetBody = () => {
    setTab('record')
    namePaging.reset()
    sitePaging.reset()
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
              {business?.business_name ?? t('business.record_title')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {business?.license_no ?? ''}
            </Typography>
          </Box>

          {business !== undefined && (
            <>
              <Stack direction="row" spacing={1}>
                <Label variant="soft" color={business.status === 'ACTIVE' ? 'success' : 'default'}>
                  {t(`business.status.${business.status}`)}
                </Label>
                {business.industry_name !== null && (
                  <Label variant="soft" color="info">
                    {business.industry_name}
                  </Label>
                )}
                {business.district !== null && (
                  <Label variant="soft" color="default">
                    {business.district}
                  </Label>
                )}
              </Stack>

              <Typography variant="caption" color="text.secondary">
                {t('business.detail_audit', { derived: formatDateTime(business.updated_at) })}
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
            label={t(`business.tabs.${name}`)}
            icon={<Iconify name={TAB_ICONS[name]} />}
          />
        ))}
      </Tabs>

      <DialogContent sx={{ minHeight: BODY_MIN_HEIGHT, bgcolor: 'background.neutral', p: 3 }}>
        <Stack spacing={RECORD_SURFACE.SECTION_GAP}>
          {query.isLoading && (
            <Stack alignItems="center" sx={{ py: 6 }}>
              <CircularProgress />
            </Stack>
          )}

          {business !== undefined && tab === 'record' && (
            <DetailSection name="info" title={t('business.tabs.record')}>
              <Grid container spacing={2}>
                {DATE_FIELDS.map((field) => (
                  <Grid key={field} size={{ xs: 12, sm: 6 }}>
                    <DetailField label={t(`business.table.${field}`)}>
                      {portalDate(business[field])}
                    </DetailField>
                  </Grid>
                ))}
                {RECORD_FIELDS.map((field) => (
                  <Grid key={field} size={{ xs: 12, sm: 6 }}>
                    <DetailField label={t(`business.field.${field}`)}>
                      {business[field]}
                    </DetailField>
                  </Grid>
                ))}
              </Grid>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
                {t('business.relation_caveat')}
              </Typography>
            </DetailSection>
          )}
          {business !== undefined && tab === 'same_name' && (
            <FoodBusinessRelatedTab
              icon="layers"
              title={t('business.tabs.same_name')}
              paging={namePaging}
            />
          )}
          {business !== undefined && tab === 'same_site' && (
            <FoodBusinessRelatedTab
              icon="link"
              title={t('business.tabs.same_site')}
              paging={sitePaging}
            />
          )}
        </Stack>
      </DialogContent>
    </Dialog>
  )
}
