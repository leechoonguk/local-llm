/**
 * Account menu, ported from the reference application's header.
 *
 * The avatar *is* the button, and the session's identity plus the way out live
 * inside the popover. Two details are the reference's, not mine: the avatar's
 * colour is derived from the first letter of the name, so two accounts are
 * distinguishable at a glance without a photo; and logout is a plain row with a
 * secondary icon, not a red one — the destructive colour is reserved for actions
 * that delete data, and signing out deletes nothing.
 */

import { useState } from 'react'
import { Avatar, Box, Divider, IconButton, MenuItem, Typography } from '@mui/material'
import type { MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import Iconify from '@/components/iconify/Iconify'
import MenuPopover from '@/components/menu-popover/MenuPopover'
import { useAuthContext } from '@/auth/useAuthContext'

const MENU_WIDTH = 220

/**
 * The reference application's avatar palette: the initial picks the tint, so an
 * account keeps the same colour across sessions and machines.
 */
const AVATAR_COLORS = {
  primary: 'ANHLQ',
  info: 'FGTIJ',
  success: 'KDYBO',
  warning: 'PERSU',
  error: 'VWXMZ',
} as const

type AvatarColor = keyof typeof AVATAR_COLORS

export default function AccountPopover() {
  const { t } = useTranslation('nav')
  const { user, logout } = useAuthContext()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)

  const name = user?.username ?? ''
  const initial = name.charAt(0).toUpperCase()
  const color = avatarColor(initial)

  return (
    <>
      <IconButton
        onClick={(event: MouseEvent<HTMLElement>) => setAnchor(event.currentTarget)}
        sx={{ p: 0, ...(anchor !== null && { bgcolor: 'action.selected' }) }}
      >
        <Avatar
          alt={name}
          sx={
            color === undefined
              ? undefined
              : { bgcolor: `${color}.main`, color: `${color}.contrastText` }
          }
        >
          {initial}
        </Avatar>
      </IconButton>

      <MenuPopover open={anchor} onClose={() => setAnchor(null)} sx={{ width: MENU_WIDTH, p: 0 }}>
        <Box sx={{ my: 1.5, px: 2 }}>
          <Typography variant="subtitle2" noWrap>
            {name}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }} noWrap>
            {user?.email ?? ''}
          </Typography>
        </Box>

        <Divider sx={{ borderStyle: 'dashed' }} />

        <MenuItem onClick={logout} sx={{ m: 1 }}>
          <Iconify name="logout" sx={{ color: 'text.secondary' }} />
          {t('logout')}
        </MenuItem>
      </MenuPopover>
    </>
  )
}

function avatarColor(initial: string): AvatarColor | undefined {
  const entry = Object.entries(AVATAR_COLORS).find(([, letters]) => letters.includes(initial))

  return entry === undefined ? undefined : (entry[0] as AvatarColor)
}
