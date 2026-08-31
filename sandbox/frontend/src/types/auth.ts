/**
 * Auth types — mirror of `backend/app/schemas/auth.py`.
 *
 * `POST /auth/login` is an OAuth2 password form, not JSON: the field is
 * `username`, and the body is form-encoded (`app/dependencies/auth.py`).
 */

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface LoginRequest {
  username: string
  password: string
}
