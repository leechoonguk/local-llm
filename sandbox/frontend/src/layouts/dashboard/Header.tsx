/**
 * The top bar, ported from the reference application's dashboard header.
 *
 * It carries no page title — the page owns that. What sits here is what is true
 * on every screen, and it sits as icon buttons: the language flag and the
 * account avatar, each opening a popover. Two properties are load-bearing and
 * both are the reference's:
 *
 *  - the bar is transparent with a blur, so content scrolling under it stays
 *    legible instead of sliding under an opaque strip;
 *  - it *shrinks* once the page scrolls past its own height, with the height
 *    animated. A fixed bar that never reacts costs the same 92px forever, which
 *    is the whole reason the reference gives a scrolled page 32px back.
 *
 * The width subtracts the nav plus its 1px border, or the bar overhangs the
 * sidebar's divider by exactly that pixel.
 *
 * There is deliberately no search field. The reference application's search
 * navigates its own page index; this app has four screens in the sidebar, and a
 * box that searches nothing is worse than no box.
 */

import { AppBar, Stack, Toolbar } from '@mui/material'
import { alpha } from '@mui/material/styles'
import AccountPopover from '@/layouts/dashboard/AccountPopover'
import LanguagePopover from '@/layouts/dashboard/LanguagePopover'
import useOffsetTop from '@/hooks/useOffsetTop'
import { HEADER, NAV } from '@/config'

const BLUR = 6

const BAR_OPACITY = 0.8

const NAV_BORDER = 1

export default function Header() {
  const offset = useOffsetTop(HEADER.H_DESKTOP)

  return (
    <AppBar
      position="fixed"
      sx={{
        boxShadow: 'none',
        zIndex: (theme) => theme.zIndex.appBar + 1,
        backdropFilter: `blur(${BLUR}px)`,
        WebkitBackdropFilter: `blur(${BLUR}px)`,
        backgroundColor: (theme) => alpha(theme.palette.background.default, BAR_OPACITY),
        transition: (theme) =>
          theme.transitions.create(['height'], {
            duration: theme.transitions.duration.shorter,
          }),
        width: { lg: `calc(100% - ${NAV.W_DASHBOARD + NAV_BORDER}px)` },
        height: {
          xs: HEADER.H_MOBILE,
          lg: offset ? HEADER.H_DESKTOP_OFFSET : HEADER.H_DESKTOP,
        },
      }}
    >
      <Toolbar sx={{ height: 1, px: { lg: 5 } }}>
        <Stack
          direction="row"
          alignItems="center"
          spacing={{ xs: 0.5, sm: 1.5 }}
          sx={{ flexGrow: 1, justifyContent: 'flex-end' }}
        >
          <LanguagePopover />
          <AccountPopover />
        </Stack>
      </Toolbar>
    </AppBar>
  )
}
