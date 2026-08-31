/**
 * Inline icon, ported from the reference application's `Iconify`.
 *
 * The prop is a registry key, not an icon string: `<Iconify name="edit" />`. That
 * is what keeps one family and one weight across the app — the mapping lives in
 * `icons.ts`, so changing what "edit" looks like is one edit rather than a grep.
 *
 * The glyph is never the event target. `@iconify/react` re-creates the `<path>`
 * nodes when it re-renders, and inside a grid cell that happens between `mouseup`
 * and the browser's `click` dispatch — the cell re-renders when it takes focus, so
 * the node the press landed on no longer exists and no `click` is ever fired. That
 * was the dead first click on every list screen: `mousedown` and `mouseup` arrived
 * at the button, `click` did not, and the mutation log showed the paths swapping
 * 3ms after `mouseup`. `pointerEvents: 'none'` makes the button itself the target,
 * and a button element survives its own icon's re-render.
 */

import { Icon } from '@iconify/react'
import { Box } from '@mui/material'
import type { SxProps, Theme } from '@mui/material'
import { ACTION_ICONS } from '@/components/iconify/icons'
import type { ActionIcon } from '@/components/iconify/icons'

const DEFAULT_SIZE = 20

interface IconifyProps {
  name: ActionIcon
  width?: number
  sx?: SxProps<Theme>
}

export default function Iconify({ name, width = DEFAULT_SIZE, sx }: IconifyProps) {
  return (
    <Box
      component={Icon}
      icon={ACTION_ICONS[name]}
      sx={{ width, height: width, flexShrink: 0, pointerEvents: 'none', ...sx }}
    />
  )
}
