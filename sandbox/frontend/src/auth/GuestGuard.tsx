/**
 * Gate for the login route.
 *
 * A signed-in user landing on the login form has no action to take there, so
 * the guard sends them to the dashboard instead of rendering a form that would
 * replace a working session.
 */

import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuthContext } from '@/auth/useAuthContext'
import { PATHS } from '@/routes/paths'

export default function GuestGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, isInitialised } = useAuthContext()

  if (isInitialised && isAuthenticated) {
    return <Navigate to={PATHS.dashboard} replace />
  }

  return children
}
