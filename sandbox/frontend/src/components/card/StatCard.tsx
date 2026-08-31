/**
 * One number on a dashboard, ported from the reference application's widget
 * summary card.
 *
 * The icon sits in a soft tinted circle, the caption above the number, the
 * number in `h3` — the same proportion on every widget, so a row of them reads
 * as one instrument panel rather than three cards.
 *
 * Three states are all visible: loading (the value is not yet known), failed
 * (it will stay unknown) and loaded. A card that renders `0` while fetching
 * reports a fact that is not true.
 */

import { Card, Skeleton, Stack, Typography, alpha } from '@mui/material'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'

const ICON_BOX_SIZE = 56

const ICON_SIZE = 28

type StatColor = 'primary' | 'info' | 'warning'

interface StatCardProps {
  title: string
  value: number | undefined
  name: ActionIcon
  color?: StatColor
  loading: boolean
  errorLabel: string
}

export default function StatCard({
  title,
  value,
  name,
  color = 'primary',
  loading,
  errorLabel,
}: StatCardProps) {
  return (
    <Card sx={{ p: 3 }}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Stack
          alignItems="center"
          justifyContent="center"
          sx={{
            width: ICON_BOX_SIZE,
            height: ICON_BOX_SIZE,
            flexShrink: 0,
            borderRadius: '50%',
            color: `${color}.dark`,
            bgcolor: (theme) => alpha(theme.palette[color].main, 0.16),
          }}
        >
          <Iconify name={name} width={ICON_SIZE} />
        </Stack>

        <Stack spacing={0.5}>
          <Typography variant="subtitle2" color="text.secondary">
            {title}
          </Typography>

          {loading && <Skeleton width={64} height={36} />}

          {!loading && value === undefined && (
            <Typography variant="body2" color="error.main">
              {errorLabel}
            </Typography>
          )}

          {!loading && value !== undefined && <Typography variant="h3">{value}</Typography>}
        </Stack>
      </Stack>
    </Card>
  )
}
