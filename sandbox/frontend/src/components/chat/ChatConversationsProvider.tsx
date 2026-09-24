/**
 * The conversations the nav lists and the chat screen shows.
 *
 * Two components need the same facts and neither owns the other: the sidebar
 * lists the conversations and starts a new one, the screen renders the open
 * one's transcript. So they live here, above both, the way the session does
 * (`auth/AuthProvider`).
 *
 * **In memory, on purpose.** No table stands behind chat
 * (`app/services/food/chat.py`) and no history is sent with a turn, so a
 * reload starts with one empty conversation. Persisting them here would be
 * this screen claiming a memory the server does not have; what "previous
 * conversations" means is the ones opened since the app was loaded.
 */

import { createContext, useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useFoodChat } from '@/lib/api/hooks/useFood'
import type { FoodChatConversation, FoodChatTurn } from '@/types/food'

export interface ChatConversationsValue {
  /** Newest first: the nav lists them in the order they were started. */
  conversations: FoodChatConversation[]
  activeId: string
  /** The open conversation's transcript, which is what the screen renders. */
  turns: FoodChatTurn[]
  streaming: boolean
  send: (message: string) => void
  stop: () => void
  /** Opens an empty conversation, or the empty one already open. */
  startNew: () => void
  select: (id: string) => void
}

export const ChatConversationsContext = createContext<ChatConversationsValue | null>(null)

const emptyConversation = (): FoodChatConversation => ({ id: crypto.randomUUID(), turns: [] })

export default function ChatConversationsProvider({
  children,
  /** How a failure's code reads — the screen's locale, not this layer's. */
  failureSentence,
}: {
  children: ReactNode
  failureSentence: (code: string) => string
}) {
  const [conversations, setConversations] = useState<FoodChatConversation[]>(() => [
    emptyConversation(),
  ])
  const [activeId, setActiveId] = useState(() => conversations[0].id)
  /** The turn tokens are landing on, so the stream's handlers know what to write. */
  const [openTurnId, setOpenTurnId] = useState<string | null>(null)

  const writeTurn = useCallback((turnId: string, change: (turn: FoodChatTurn) => FoodChatTurn) => {
    setConversations((previous) =>
      previous.map((conversation) => ({
        ...conversation,
        turns: conversation.turns.map((turn) => (turn.id === turnId ? change(turn) : turn)),
      })),
    )
  }, [])

  const chat = useFoodChat({
    onToken: (text) => {
      if (openTurnId !== null) writeTurn(openTurnId, (turn) => ({ ...turn, text: turn.text + text }))
    },
    onEnd: (text) => {
      if (openTurnId !== null) writeTurn(openTurnId, (turn) => ({ ...turn, text, streaming: false }))
    },
    onFailure: (code) => {
      if (openTurnId === null) return
      writeTurn(openTurnId, (turn) => ({ ...turn, text: failureSentence(code), streaming: false }))
    },
  })

  const send = useCallback(
    (message: string) => {
      const asked = message.trim()
      if (asked === '' || chat.streaming) return
      const answerId = crypto.randomUUID()
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === activeId
            ? {
                ...conversation,
                turns: [
                  ...conversation.turns,
                  { id: crypto.randomUUID(), author: 'user', text: asked, streaming: false },
                  { id: answerId, author: 'assistant', text: '', streaming: true },
                ],
              }
            : conversation,
        ),
      )
      setOpenTurnId(answerId)
      void chat.ask(asked).finally(() => {
        // Whatever ended it — the end event, a failure, the reader's stop —
        // the turn is no longer being written to.
        writeTurn(answerId, (turn) => ({ ...turn, streaming: false }))
        setOpenTurnId(null)
      })
    },
    [activeId, chat, writeTurn],
  )

  const startNew = useCallback(() => {
    // An empty conversation is already a new one: starting another would
    // leave a row in the list that says nothing and opens nothing.
    const empty = conversations.find((conversation) => conversation.turns.length === 0)
    if (empty !== undefined) {
      setActiveId(empty.id)
      return
    }
    // Both writes outside the updater: an updater that also sets other state
    // is not a pure function of the previous value, and React may run it
    // twice - measured, the id it selected was not the id it inserted, and
    // the next send landed in a conversation nothing was showing.
    const started = emptyConversation()
    setConversations((previous) => [started, ...previous])
    setActiveId(started.id)
  }, [conversations])

  const value = useMemo<ChatConversationsValue>(() => {
    const active = conversations.find((conversation) => conversation.id === activeId)
    return {
      conversations,
      activeId,
      turns: active?.turns ?? [],
      streaming: chat.streaming,
      send,
      stop: chat.stop,
      startNew,
      select: setActiveId,
    }
  }, [conversations, activeId, chat.streaming, chat.stop, send, startNew])

  return (
    <ChatConversationsContext.Provider value={value}>{children}</ChatConversationsContext.Provider>
  )
}
