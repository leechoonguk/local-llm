/**
 * The authenticated shell, ported from the reference application.
 *
 * The header is fixed, so the main column's top padding is derived from the
 * header height plus one gap — never a literal, or content sits under the bar on
 * whichever screen was not adjusted. The guard is part of the layout, so a page
 * added here is authenticated by construction.
 */

import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import AuthGuard from '@/auth/AuthGuard'
import Header from '@/layouts/dashboard/Header'
import NavVertical from '@/layouts/dashboard/NavVertical'
import { HEADER, MAIN_SPACING } from '@/config'

export default function DashboardLayout() {
  return (
    <AuthGuard>
      <Header />

      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        <NavVertical />

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
    </AuthGuard>
  )
}
