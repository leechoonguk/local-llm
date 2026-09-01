/**
 * Auth service — the transport half of login.
 *
 * `POST /auth/login` is an OAuth2 password *form*, so this is the one place in
 * the app that sends `application/x-www-form-urlencoded`.
 */

import { api } from '@/lib/api/client'
import { AUTH_ENDPOINTS } from '@/lib/api/endpoints'
import type { LoginRequest, LogoutResponse, TokenResponse } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>(
      AUTH_ENDPOINTS.LOGIN,
      new URLSearchParams({ username: data.username, password: data.password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    ),

  me: () => api.get<User>(AUTH_ENDPOINTS.ME),

  // The credential is the httpOnly cookie the browser attaches on its own —
  // the empty body is the schema's whole contract (SessionRequest).
  refresh: () => api.post<TokenResponse>(AUTH_ENDPOINTS.REFRESH, {}),

  // The credential is the httpOnly cookie, not anything in the body — the
  // empty object is the schema's whole contract (SessionRequest).
  logout: () => api.post<LogoutResponse>(AUTH_ENDPOINTS.LOGOUT, {}),
}
