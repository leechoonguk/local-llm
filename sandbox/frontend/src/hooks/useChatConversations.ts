/**
 * The conversations accessor.
 *
 * The throw is the contract: a component rendered outside the provider would
 * otherwise read `null` and quietly behave as if there were no conversation.
 */

import { useContext } from 'react'
import { ChatConversationsContext } from '@/components/chat/ChatConversationsProvider'
import type { ChatConversationsValue } from '@/components/chat/ChatConversationsProvider'

export function useChatConversations(): ChatConversationsValue {
  const context = useContext(ChatConversationsContext)
  if (context === null) {
    throw new Error('useChatConversations must be used inside ChatConversationsProvider')
  }
  return context
}
