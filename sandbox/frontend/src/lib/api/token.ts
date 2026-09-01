/**
 * Access-token storage and the session-expiry signal.
 *
 * The backend issues a short-lived bearer access token; the long-lived half of
 * the session is an httpOnly cookie the page cannot read (`app/routers/auth.py`).
 * Only the access token lives here, and `sessionStorage` is the honest place
 * for it: it survives a reload, dies with the tab, and is never sent
 * automatically by the browser to anyone — expiry is the interceptor's cue to
 * spend the cookie via the registered session refresher.
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
