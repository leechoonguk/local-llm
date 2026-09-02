/**
 * The dashboard template — independent widgets, each owning its own query.
 *
 * One widget failing must not blank the page, so there is no shared "is the
 * dashboard loading" state: every card reports its own loading, its own failure
 * and its own number.
 *
 * Each card reads `total` from the list endpoint's `Page<T>` and asks for the
 * smallest page the API allows, because it wants the number and not the rows.
 * Before the envelope there was no total to read: the card fetched 100 whole
 * rows per widget and displayed `data.length`, which stopped being the count as
 * soon as a collection outgrew one page — three cards, 300 rows, to render
 * three integers that were wrong past 100.
 */

import { Grid } from '@mui/material'
import { useTranslation } from 'react-i18next'
import StatCard from '@/components/card/StatCard'
import { useBatchList } from '@/lib/api/hooks/useBatch'
import { useIntegrationList } from '@/lib/api/hooks/useIntegration'
import { useUserList } from '@/lib/api/hooks/useUser'

/** One row: `limit` is bounded at 1 by the API, and the count is not in the rows. */
const COUNT_PARAMS = { offset: 0, limit: 1 }

export default function DashboardView() {
  const { t } = useTranslation('dashboard')

  const users = useUserList(COUNT_PARAMS)
  const batches = useBatchList(COUNT_PARAMS)
  const integrations = useIntegrationList(COUNT_PARAMS)

  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          title={t('widgets.users')}
          value={users.data?.total}
          name="people"
          color="primary"
          loading={users.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          title={t('widgets.batches')}
          value={batches.data?.total}
          name="layers"
          color="info"
          loading={batches.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          title={t('widgets.integrations')}
          value={integrations.data?.total}
          name="link"
          color="warning"
          loading={integrations.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
    </Grid>
  )
}
