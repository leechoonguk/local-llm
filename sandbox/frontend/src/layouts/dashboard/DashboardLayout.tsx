/**
 * The authenticated shell, ported from the reference application.
 *
 * The header is fixed, so the main column's top padding is derived from the
 * header height plus one gap — never a literal, or content sits under the bar on
 * whichever screen was not adjusted. The guard is part of the layout, so a page
 * added here is authenticated by construction.
 *
 * The nav is docked from `lg` up and a drawer below it, opened from the header's
 * menu button: the shell is one code path on a phone, a tablet and a desktop,
 * and the breakpoint is the header's own. Measured before this: a permanent
 * 280px nav at 390px left the content 78px wide, and at 820px a third of the
 * screen.
 *
 * The chat conversations live at this level because the nav lists them and a
 * page renders one: two children of this shell, neither owning the other.
 */

import { useCallback, useState } from 'react'
import { Box } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'
import AuthGuard from '@/auth/AuthGuard'
import ChatConversationsProvider from '@/components/chat/ChatConversationsProvider'
import { serverErrorMessage } from '@/lib/api/formErrors'
import Header from '@/layouts/dashboard/Header'
import NavVertical from '@/layouts/dashboard/NavVertical'
import { HEADER, MAIN_SPACING } from '@/config'

export default function DashboardLayout() {
  const [navOpen, setNavOpen] = useState(false)
  const { t: tCommon } = useTranslation('common')
  // One place words a failure, whether it arrived as an event or as a status.
  const failureSentence = useCallback(
    (code: string) => serverErrorMessage(code, tCommon),
    [tCommon],
  )

  return (
    <AuthGuard>
      <ChatConversationsProvider failureSentence={failureSentence}>
        <Header onOpenNav={() => setNavOpen(true)} />

        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
          <NavVertical open={navOpen} onClose={() => setNavOpen(false)} />

          <Box
            component="main"
            sx={{
              // The permanent drawer already occupies its width in this flex row,
              // so main only grows into what is left. Subtracting the nav width
              // here as well squeezed the content into a narrow strip.
              flexGrow: 1,
              minWidth: 0,
              bgcolor: 'background.neutral',
              px: { xs: 2, lg: 5 },
              pt: { xs: `${HEADER.H_MOBILE + MAIN_SPACING}px`, lg: `${HEADER.H_DESKTOP + MAIN_SPACING}px` },
              pb: { xs: 4, lg: 8 },
            }}
          >
            <Outlet />
          </Box>
        </Box>
      </ChatConversationsProvider>
    </AuthGuard>
  )
}
