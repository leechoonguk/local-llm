/**
 * The dashboard template — independent widgets, each owning its own query.
 *
 * One widget failing must not blank the page, so there is no shared "is the
 * dashboard loading" state: every card reports its own loading, its own failure
 * and its own number.
 *
 * The counts are honest about what this API can answer. No endpoint returns a
 * total, so a card shows "the first page and whether more exist" (`12+`) rather
 * than inventing a total by paging the whole collection.
 */

import { Grid } from '@mui/material'
import { useTranslation } from 'react-i18next'
import StatCard from '@/components/card/StatCard'
import { MAX_PAGE_SIZE } from '@/config'
import { useBatchList } from '@/lib/api/hooks/useBatch'
import { useIntegrationList } from '@/lib/api/hooks/useIntegration'
import { useUserList } from '@/lib/api/hooks/useUser'

const COUNT_PARAMS = { offset: 0, limit: MAX_PAGE_SIZE }

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
          value={users.data?.length}
          name="people"
          color="primary"
          loading={users.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          title={t('widgets.batches')}
          value={batches.data?.length}
          name="layers"
          color="info"
          loading={batches.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          title={t('widgets.integrations')}
          value={integrations.data?.length}
          name="link"
          color="warning"
          loading={integrations.isLoading}
          errorLabel={t('unavailable')}
        />
      </Grid>
    </Grid>
  )
}
