/**
 * One label/value pair inside a detail section, ported from the reference
 * application.
 *
 * The label is `caption` in secondary text above the value, never beside it: a
 * two-column label/value table breaks at narrow widths, while a stacked pair
 * reflows. An absent value renders a dash, so a blank cell always means "no
 * value" rather than "did not load".
 */

import { Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'

const EMPTY_VALUE = '-'

interface DetailFieldProps {
  label: string
  children?: ReactNode
}

export default function DetailField({ label, children }: DetailFieldProps) {
  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" component="div">
        {children ?? EMPTY_VALUE}
      </Typography>
    </Stack>
  )
}
