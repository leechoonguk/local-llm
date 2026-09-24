/**
 * The 식품 챗 screen — the conversations beside the one being read.
 *
 * Ported from the reference application's chat: **one card, two columns**. The
 * left column is the history and the right is the open conversation, with the
 * composer pinned under it. The reference's left column lists *people*; there
 * are none here — nobody is on the other end but the model — so it lists the
 * conversations themselves, titled by the first thing the reader said in each.
 *
 * The history moved out of the sidebar in the same edit. It was a list of one
 * screen's destinations sitting among the app's destinations, which is why it
 * had to fold itself away whenever the reader was somewhere else; inside the
 * screen it is simply always there, and the sidebar is back to being a list of
 * screens.
 *
 * Not a list screen: there is no collection, no page and no filter, so none of
 * the list template's five pieces apply. What it owns is a transcript, an input,
 * and the one request in flight.
 *
 * **The answer is streamed, and the screen shows that.** The service yields
 * server-sent events (`api.stream`); a `token` appends to the open turn, the one
 * `end` closes it with the server's own whole answer - the authority, in case a
 * token was dropped - and an `error` turns the open turn into the failure's
 * sentence. A turn that simply stopped would be indistinguishable from a lost
 * network, which is why the server ends every turn with an event.
 *
 * The right column has **no title bar**: the conversation's name is the history
 * row that opened it, a hand's width to the left, and repeating it above the
 * transcript spent a line on something already on screen. That the model is
 * answering is said where it is happening — a spinner on the turn being written,
 * and the composer's send turning into a stop.
 *
 * Nothing is stored: no table behind it, no history sent back, so a reload is an
 * empty transcript and the answer is a function of the message alone.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Box,
  Card,
  CircularProgress,
  Divider,
  IconButton,
  InputAdornment,
  ListItemButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { alpha } from '@mui/material/styles'
import Iconify from '@/components/iconify/Iconify'
import { useChatConversations } from '@/hooks/useChatConversations'
import type { FoodChatConversation as Conversation } from '@/types/food'

/**
 * The card's own height: the two columns scroll inside it, the page does not.
 *
 * A screen whose composer moves down as the answer grows makes the reader chase
 * the box they are typing into — the reference pins it, and pinning needs a
 * surface with a height.
 */
const CHAT_HEIGHT = 640

/**
 * The history column.
 *
 * Narrower than the reference's 320: its rows carry an avatar, a name, a last
 * message and a time, and these carry two lines of text. 260 fits a question of
 * roughly twenty Hangul syllables before the ellipsis, and gives the width back
 * to the transcript, which is what the reader is actually reading.
 */
const HISTORY_WIDTH = 260

/** A turn's bubble never runs the full width — a wall of text has no speaker. */
const BUBBLE_MAX_WIDTH = '76%'

export default function FoodChatConversation() {
  const { t } = useTranslation('food')

  const [draft, setDraft] = useState('')
  const transcript = useRef<HTMLDivElement | null>(null)
  // The transcript belongs to the conversation the history has open, so it
  // lives above both (`ChatConversationsProvider`) and this renders what it holds.
  const chat = useChatConversations()
  const { turns, streaming } = chat

  // The newest line is the one being written: follow it as tokens land.
  useEffect(() => {
    const node = transcript.current
    if (node !== null) node.scrollTop = node.scrollHeight
  }, [turns])

  const send = () => {
    chat.send(draft)
    setDraft('')
  }

  // Every conversation but the empty one the "new" row already is.
  const started = chat.conversations.filter((conversation) => conversation.turns.length > 0)

  return (
    <Card sx={{ display: 'flex', height: CHAT_HEIGHT, overflow: 'hidden' }}>
      <Stack
        sx={{
          width: HISTORY_WIDTH,
          flexShrink: 0,
          borderRight: (theme) => `1px dashed ${theme.palette.divider}`,
          display: { xs: 'none', md: 'flex' },
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{ px: 2.5, py: 2 }}
        >
          <Typography variant="subtitle1">{t('chat.history')}</Typography>
          <Tooltip title={t('chat.new')}>
            <IconButton color="primary" onClick={chat.startNew}>
              <Iconify name="add" />
            </IconButton>
          </Tooltip>
        </Stack>

        <Divider />

        <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 1 }}>
          {started.length === 0 && (
            <Typography variant="body2" sx={{ color: 'text.secondary', p: 1.5 }}>
              {t('chat.history_empty')}
            </Typography>
          )}

          {started.map((conversation) => (
            <HistoryRow
              key={conversation.id}
              conversation={conversation}
              selected={conversation.id === chat.activeId}
              onSelect={() => chat.select(conversation.id)}
            />
          ))}
        </Box>
      </Stack>

      <Stack sx={{ flexGrow: 1, minWidth: 0 }}>
        <Box ref={transcript} sx={{ flexGrow: 1, overflowY: 'auto', p: 2.5 }}>
          {turns.length === 0 ? (
            <Stack alignItems="center" justifyContent="center" sx={{ height: 1 }} spacing={1}>
              <Typography variant="h6">{t('chat.empty')}</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {t('chat.empty_hint')}
              </Typography>
            </Stack>
          ) : (
            <Stack spacing={1.5}>
              {turns.map((turn) => (
                <Stack
                  key={turn.id}
                  spacing={0.5}
                  sx={{ alignItems: turn.author === 'user' ? 'flex-end' : 'flex-start' }}
                >
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {turn.author === 'user' ? t('chat.you') : t('chat.assistant')}
                  </Typography>
                  <Box
                    sx={{
                      maxWidth: BUBBLE_MAX_WIDTH,
                      px: 2,
                      py: 1,
                      borderRadius: 1.5,
                      // The reader's own words carry the primary tint; the
                      // answer sits on the page's neutral surface, which is the
                      // pair the reference uses and the only one that holds in
                      // both modes.
                      bgcolor:
                        turn.author === 'user'
                          ? (theme) => alpha(theme.palette.primary.main, 0.16)
                          : 'background.neutral',
                    }}
                  >
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                      {turn.text}
                      {turn.streaming && turn.text === '' && (
                        <CircularProgress size={14} sx={{ ml: 0.5 }} />
                      )}
                    </Typography>
                  </Box>
                </Stack>
              ))}
            </Stack>
          )}
        </Box>

        <Divider />

        {/*
          The verb lives inside the box, as an end adornment: the input is the
          whole row, and a button beside it took width from the thing being
          typed into for no gain — there is one action and its target is the
          text under it.
        */}
        <Box sx={{ p: 2 }}>
          <TextField
            fullWidth
            size="small"
            multiline
            maxRows={4}
            placeholder={t('chat.placeholder')}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            // Enter sends, Shift+Enter is a newline: the box is a message, not a form.
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                send()
              }
            }}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    {streaming ? (
                      <IconButton aria-label={t('chat.stop')} color="error" onClick={chat.stop}>
                        <Iconify name="stop" />
                      </IconButton>
                    ) : (
                      <IconButton
                        aria-label={t('chat.send')}
                        color="primary"
                        disabled={draft.trim() === ''}
                        onClick={send}
                      >
                        <Iconify name="run" />
                      </IconButton>
                    )}
                  </InputAdornment>
                ),
              },
            }}
          />
        </Box>
      </Stack>
    </Card>
  )
}

interface HistoryRowProps {
  conversation: Conversation
  selected: boolean
  onSelect: () => void
}

/**
 * One conversation in the history: what was asked, and what came back last.
 *
 * The reference's row is a person, a last message and a time. There is no
 * person here and no clock behind the turns, so the row is what the
 * conversation actually holds — the reader's first question as its name, and
 * the newest line under it, which is how a reader recognises the one they left.
 */
function HistoryRow({ conversation, selected, onSelect }: HistoryRowProps) {
  const latest = conversation.turns[conversation.turns.length - 1]

  return (
    <ListItemButton
      selected={selected}
      onClick={onSelect}
      sx={{ borderRadius: 1, mb: 0.5, display: 'block', py: 1 }}
    >
      <Typography variant="subtitle2" noWrap>
        {conversation.turns[0].text}
      </Typography>
      <Typography variant="caption" noWrap sx={{ color: 'text.secondary', display: 'block' }}>
        {latest.text}
      </Typography>
    </ListItemButton>
  )
}
