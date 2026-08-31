/**
 * Access-token storage and the session-expiry signal.
 *
 * The backend issues a bearer access token and nothing else — there is no
 * refresh endpoint and no httpOnly cookie (`app/routers/auth.py`), so a token
 * held only in memory would log the user out on every reload. `sessionStorage`
 * is the honest middle: it survives a reload, dies with the tab, and is never
 * sent automatically by the browser to anyone.
 *
 * The interceptor cannot navigate (it is outside React), so it publishes one
 * event and `AuthProvider` owns the redirect.
 */

const STORAGE_KEY = 'access_token'

const SESSION_EXPIRED_EVENT = 'auth:session-expired'

export function getAccessToken(): string | null {
  return sessionStorage.getItem(STORAGE_KEY)
}

export function setAccessToken(token: string | null): void {
  if (token === null) {
    sessionStorage.removeItem(STORAGE_KEY)
    return
  }
  sessionStorage.setItem(STORAGE_KEY, token)
}

export function emitSessionExpired(): void {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
}

/** Returns the unsubscribe function so an effect can clean itself up. */
export function onSessionExpired(listener: () => void): () => void {
  window.addEventListener(SESSION_EXPIRED_EVENT, listener)
  return () => window.removeEventListener(SESSION_EXPIRED_EVENT, listener)
}
