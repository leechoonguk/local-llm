/**
 * The empty state of a list, ported from the reference application's
 * `EmptyContent`.
 *
 * An illustration with an `h5` line, not an icon with small grey text: the empty
 * state is the whole screen at that moment, and a 20px glyph reads as a loading
 * artefact rather than an answer. The sentence comes from the screen, because
 * "no rows yet" and "the filter matched nothing" are different answers.
 */

import { Box, Stack, Typography } from '@mui/material'
import { EMPTY_CONTENT_ILLUSTRATION } from '@/components/iconify/icons'

const ILLUSTRATION_HEIGHT = 200

export default function DataGridEmptyOverlay({ title }: { title: string }) {
  return (
    <Stack alignItems="center" justifyContent="center" sx={{ height: 1, p: (theme) => theme.spacing(6, 2) }}>
      <Box
        component="img"
        alt=""
        src={EMPTY_CONTENT_ILLUSTRATION}
        sx={{ height: ILLUSTRATION_HEIGHT, mb: 2 }}
      />

      <Typography variant="h5">{title}</Typography>
    </Stack>
  )
}
