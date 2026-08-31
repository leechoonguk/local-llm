/**
 * The sidebar, ported from the reference application's vertical nav section.
 *
 * The design is specific and every part of it carries meaning: a 280px column
 * with a dashed right border, `overline`-styled subheaders, 48px items with an
 * 8px radius, and an active item tinted with 16%-alpha primary and primary text.
 * The active state comes from `NavLink`, never from comparing `useLocation` by
 * hand — that is how two items end up looking selected.
 */

import { Box, Drawer, List, ListItemButton, ListItemText, Stack, Typography } from '@mui/material'
import { alpha, styled } from '@mui/material/styles'
import type { ElementType } from 'react'
import { NavLink } from 'react-router-dom'
import SvgColor from '@/components/svg-color/SvgColor'
import { BRAND_MARK, NAV_ICONS } from '@/components/iconify/icons'
import { useTranslation } from 'react-i18next'
import { ICON, NAV } from '@/config'
import { NAV_GROUPS } from '@/layouts/dashboard/config-navigation'

const SUBHEADER_FONT_SIZE = 11

const StyledItem = styled(ListItemButton)<{ component?: ElementType; to?: string }>(({ theme }) => ({
  height: NAV.H_ITEM,
  marginBottom: theme.spacing(0.5),
  paddingLeft: theme.spacing(2),
  paddingRight: theme.spacing(1.5),
  borderRadius: theme.shape.borderRadius,
  color: theme.palette.text.secondary,
  '&.active': {
    color: theme.palette.primary.main,
    backgroundColor: alpha(theme.palette.primary.main, 0.16),
    '& .MuiListItemText-primary': { fontWeight: theme.typography.fontWeightBold },
    '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.16) },
  },
}))

export default function NavVertical() {
  const { t } = useTranslation('nav')

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: NAV.W_DASHBOARD,
        flexShrink: 0,
        '& .MuiDrawer-paper': { width: NAV.W_DASHBOARD, bgcolor: 'background.default' },
      }}
    >
      <Stack sx={{ px: 2, py: 3 }} direction="row" alignItems="center" spacing={1}>
        <SvgColor src={BRAND_MARK} sx={{ width: 32, height: 32, color: 'primary.main' }} />
        <Typography variant="subtitle1">{t('brand')}</Typography>
      </Stack>

      <Box sx={{ px: 2 }}>
        {NAV_GROUPS.map((group) => (
          <List key={group.subheaderKey} disablePadding>
            <Typography
              variant="overline"
              sx={{
                display: 'block',
                fontSize: SUBHEADER_FONT_SIZE,
                color: 'text.secondary',
                pt: 3,
                pb: 1,
              }}
            >
              {t(group.subheaderKey)}
            </Typography>

            {group.items.map((item) => (
              <StyledItem key={item.path} component={NavLink} to={item.path} disableGutters>
                <Box
                  sx={{
                    width: ICON.NAV_ITEM,
                    height: ICON.NAV_ITEM,
                    mr: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <SvgColor src={NAV_ICONS[item.icon]} />
                </Box>
                <ListItemText
                  primary={t(item.titleKey)}
                  slotProps={{ primary: { noWrap: true, variant: 'body2' } }}
                />
              </StyledItem>
            ))}
          </List>
        ))}
      </Box>
    </Drawer>
  )
}
