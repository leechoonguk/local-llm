/**
 * Gate for every authenticated route.
 *
 * Every endpoint but login requires a bearer token (`CurrentUserDep` on all of
 * them), so an unauthenticated render would only produce a screen full of 401s.
 * The attempted path is carried in the redirect state so login can return the
 * user where they were going.
 */

import { CircularProgress, Stack } from '@mui/material'
import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuthContext } from '@/auth/useAuthContext'
import { PATHS } from '@/routes/paths'

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isInitialised } = useAuthContext()
  const location = useLocation()

  if (!isInitialised) {
    return (
      <Stack alignItems="center" justifyContent="center" sx={{ height: '100vh' }}>
        <CircularProgress />
      </Stack>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to={PATHS.auth.login} state={{ from: location.pathname }} replace />
  }

  return children
}
