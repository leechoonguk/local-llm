/**
 * The catch-all route.
 *
 * A URL that matches nothing must say so and offer the way back; a silent blank
 * page is indistinguishable from a crash.
 */

import { Button, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PATHS } from '@/routes/paths'

const NOT_FOUND_STATUS = 404

export default function NotFoundPage() {
  const { t } = useTranslation('nav')

  return (
    <Stack alignItems="center" justifyContent="center" spacing={2} sx={{ height: '100vh' }}>
      <Typography variant="h4">{NOT_FOUND_STATUS}</Typography>
      <Button component={RouterLink} to={PATHS.dashboard} variant="contained">
        {t('dashboard')}
      </Button>
    </Stack>
  )
}
