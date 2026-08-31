/**
 * Auth service — the transport half of login.
 *
 * `POST /auth/login` is an OAuth2 password *form*, so this is the one place in
 * the app that sends `application/x-www-form-urlencoded`.
 */

import { api } from '@/lib/api/client'
import { AUTH_ENDPOINTS } from '@/lib/api/endpoints'
import type { LoginRequest, TokenResponse } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>(
      AUTH_ENDPOINTS.LOGIN,
      new URLSearchParams({ username: data.username, password: data.password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    ),

  me: () => api.get<User>(AUTH_ENDPOINTS.ME),
}
