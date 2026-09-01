/**
 * Session state for the whole app.
 *
 * There are exactly three states and the difference matters: *initialising*
 * (a token exists and `GET /auth/me` has not answered yet), *authenticated*,
 * and *anonymous*. A guard that cannot tell the first from the third bounces a
 * signed-in user to the login page on every reload.
 */

import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { authService } from '@/lib/api/services/auth.service'
import { getAccessToken, onSessionExpired, setAccessToken } from '@/lib/api/token'
import { setSessionRefresher } from '@/lib/api/client'
import type { User } from '@/types/user'

interface AuthState {
  user: User | null
  isInitialised: boolean
}

export interface AuthContextValue extends AuthState {
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export default function AuthProvider({ children }: { children: ReactNode }) {
  // No token means there is nothing to restore, so the session is already
  // resolved at mount — deciding that in an effect would render one frame of
  // "still initialising" and cascade a second render for no new information.
  const [state, setState] = useState<AuthState>(() => ({
    user: null,
    isInitialised: getAccessToken() === null,
  }))

  useEffect(() => {
    if (getAccessToken() === null) return
    let cancelled = false
    authService
      .me()
      .then((user) => {
        if (!cancelled) setState({ user, isInitialised: true })
      })
      .catch(() => {
        // The stored token is no longer accepted; treat the session as anonymous.
        setAccessToken(null)
        if (!cancelled) setState({ user: null, isInitialised: true })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // The interceptor cannot import the service layer (the service imports the
  // client), so the session-refresh transport is handed over here, once.
  useEffect(() => {
    setSessionRefresher(() => authService.refresh().then((token) => token.access_token))
  }, [])

  useEffect(
    () =>
      onSessionExpired(() => {
        setState({ user: null, isInitialised: true })
      }),
    [],
  )

  const login = useCallback(async (username: string, password: string) => {
    const token = await authService.login({ username, password })
    setAccessToken(token.access_token)
    const user = await authService.me()
    setState({ user, isInitialised: true })
  }, [])

  const logout = useCallback(() => {
    // Best-effort server-side revocation: the cookie's session dies even if
    // this tab never comes back. Local sign-out proceeds regardless — a network
    // failure must not trap the user in a session they asked to leave.
    void authService.logout().catch(() => undefined)
    setAccessToken(null)
    setState({ user: null, isInitialised: true })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: state.user,
      isInitialised: state.isInitialised,
      isAuthenticated: state.user !== null,
      login,
      logout,
    }),
    [state.user, state.isInitialised, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
