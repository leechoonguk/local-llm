/**
 * The unauthenticated shell, ported from the reference application's login
 * layout.
 *
 * Two panes: an illustration section that appears from `md` up, and a 480px
 * content column that holds the form. The section is not decoration — it is what
 * makes the sign-in page read as the product's front door rather than a form on
 * a blank page, and it disappears on a phone where the form needs the width.
 *
 * `GuestGuard` lives here so every future public screen (password reset, sign
 * up) inherits the same "already signed in? go to the app" behaviour.
 */

import { Box, Stack, Typography } from '@mui/material'
import { alpha, styled } from '@mui/material/styles'
import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import GuestGuard from '@/auth/GuestGuard'
import SvgColor from '@/components/svg-color/SvgColor'
import { BRAND_MARK, LOGIN_BACKGROUND, LOGIN_ILLUSTRATION } from '@/components/iconify/icons'

const CONTENT_WIDTH = 480

const ILLUSTRATION_MAX_WIDTH = 720

const BRAND_SIZE = 40

const StyledRoot = styled('main')({
  height: '100%',
  display: 'flex',
  position: 'relative',
})

const StyledSection = styled('div')(({ theme }) => ({
  display: 'none',
  position: 'relative',
  [theme.breakpoints.up('md')]: {
    flexGrow: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'column',
  },
}))

const StyledSectionBackground = styled('div')(({ theme }) => ({
  top: 0,
  left: 0,
  zIndex: -1,
  width: '100%',
  height: '100%',
  position: 'absolute',
  transform: 'scaleX(-1)',
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  backgroundImage: `linear-gradient(to bottom, ${alpha(
    theme.palette.background.default,
    0.9,
  )}, ${alpha(theme.palette.background.default, 0.9)}), url(${LOGIN_BACKGROUND})`,
}))

const StyledContent = styled('div')(({ theme }) => ({
  width: CONTENT_WIDTH,
  margin: 'auto',
  display: 'flex',
  minHeight: '100vh',
  justifyContent: 'center',
  alignItems: 'center',
  padding: theme.spacing(15, 2),
  [theme.breakpoints.up('md')]: {
    flexShrink: 0,
    padding: theme.spacing(0, 8),
  },
}))

export default function AuthLayout() {
  const { t } = useTranslation('auth')

  return (
    <GuestGuard>
      <StyledRoot>
        <Box sx={{ zIndex: 9, position: 'absolute', mt: { xs: 1.5, md: 5 }, ml: { xs: 2, md: 5 } }}>
          <SvgColor
            src={BRAND_MARK}
            sx={{ width: BRAND_SIZE, height: BRAND_SIZE, color: 'primary.main' }}
          />
        </Box>

        <StyledSection>
          <Typography
            variant="h3"
            sx={{ mb: 10, maxWidth: 480, textAlign: 'center', wordBreak: 'keep-all' }}
          >
            {t('login.welcome')}
          </Typography>

          <Box
            component="img"
            alt=""
            src={LOGIN_ILLUSTRATION}
            sx={{ maxWidth: ILLUSTRATION_MAX_WIDTH, width: 1 }}
          />

          <StyledSectionBackground />
        </StyledSection>

        <StyledContent>
          <Stack sx={{ width: 1 }}>
            <Outlet />
          </Stack>
        </StyledContent>
      </StyledRoot>
    </GuestGuard>
  )
}
