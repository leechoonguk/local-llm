/**
 * Session accessor.
 *
 * The throw is the contract: a component rendered outside `AuthProvider` would
 * otherwise read `null` and quietly behave as if nobody were signed in.
 */

import { useContext } from 'react'
import { AuthContext } from '@/auth/AuthProvider'
import type { AuthContextValue } from '@/auth/AuthProvider'

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuthContext must be used inside AuthProvider')
  }
  return context
}
