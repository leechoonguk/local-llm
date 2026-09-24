/**
 * The bell, ported from the reference application's header.
 *
 * It reports one thing, because one thing in this app happens while nobody is
 * looking: a scheduled run that failed overnight. Everything else a screen shows
 * is the result of something the reader just did, and a toast already answers
 * that. So the badge counts recent failed runs and the list names them — the
 * schedule, how it ended, when, and the code it failed with.
 *
 * Each row opens that schedule's own run log (`/batch?runs=<id>`), which is
 * where the steps, the durations and the error detail already live. A
 * notification that only said "something failed" would leave the reader to find
 * the schedule by hand, and a second copy of the log here would be a log that
 * can disagree with the one on the batch screen.
 *
 * There is no read/unread state: that is a per-user table the backend does not
 * have, and a "mark as read" kept in this tab would report differently on the
 * next machine. The window is what makes the count fall to zero instead.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Box, Divider, IconButton, MenuItem, Stack, Typography } from '@mui/material'
import type { MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'
import MenuPopover from '@/components/menu-popover/MenuPopover'
import { useBatchFailureFeed } from '@/lib/api/hooks/useBatch'
import { PATHS } from '@/routes/paths'
import { formatDateTime } from '@/utils/formatTime'

const MENU_WIDTH = 360

/** Past this the list scrolls; the badge still counts them all. */
const LIST_MAX_HEIGHT = 320

export default function NotificationsPopover() {
  const { t } = useTranslation('batch')
  const navigate = useNavigate()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const { failures } = useBatchFailureFeed()

  // The log is the batch screen's, opened by the URL: a dialog the header owned
  // would be a second run log that can disagree with the one on that screen.
  const openRuns = (batchId: string) => {
    setAnchor(null)
    void navigate(`${PATHS.batch}?runs=${batchId}`)
  }

  const openSchedules = () => {
    setAnchor(null)
    void navigate(PATHS.batch)
  }

  return (
    <>
      <IconButton
        onClick={(event: MouseEvent<HTMLElement>) => setAnchor(event.currentTarget)}
        aria-label={t('notifications.open')}
        sx={{ color: 'text.primary', ...(anchor !== null && { bgcolor: 'action.selected' }) }}
      >
        <Badge badgeContent={failures.length} color="error">
          <Iconify name="bell" />
        </Badge>
      </IconButton>

      <MenuPopover open={anchor} onClose={() => setAnchor(null)} sx={{ width: MENU_WIDTH, p: 0 }}>
        <Box sx={{ my: 1.5, px: 2 }}>
          <Typography variant="subtitle2">{t('notifications.title')}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {t('notifications.subtitle')}
          </Typography>
        </Box>

        <Divider sx={{ borderStyle: 'dashed' }} />

        {failures.length === 0 && (
          <Typography variant="body2" sx={{ color: 'text.secondary', p: 2 }}>
            {t('notifications.empty')}
          </Typography>
        )}

        <Box sx={{ maxHeight: LIST_MAX_HEIGHT, overflowY: 'auto' }}>
          {failures.map((failure) => (
            <MenuItem key={failure.run.id} onClick={() => openRuns(failure.batch.id)} sx={{ m: 1 }}>
              <Stack spacing={0.5} sx={{ width: 1, py: 0.5 }}>
                <Stack direction="row" alignItems="center" spacing={1} useFlexGap>
                  <Typography variant="subtitle2" noWrap sx={{ flexGrow: 1 }}>
                    {failure.batch.code}
                  </Typography>
                  <Label color="error">{t(`runs.status.${failure.run.status}`)}</Label>
                </Stack>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {formatDateTime(failure.run.started_at)}
                  {failure.run.error_code !== null && ` · ${failure.run.error_code}`}
                </Typography>
              </Stack>
            </MenuItem>
          ))}
        </Box>

        <Divider sx={{ borderStyle: 'dashed' }} />

        <MenuItem onClick={openSchedules} sx={{ m: 1, justifyContent: 'center' }}>
          <Typography variant="body2">{t('notifications.view_all')}</Typography>
        </MenuItem>
      </MenuPopover>
    </>
  )
}
