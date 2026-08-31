/**
 * Component defaults, ported from the reference application's `theme/overrides`.
 *
 * This is where the design lives. Every value here was previously repeated in
 * component `sx` props — a card's radius, a dialog's shadow, a table header's
 * background — and repetition is how twelve cards end up with eleven radii. A
 * screen sets layout; the theme sets appearance.
 */

import { alpha } from '@mui/material/styles'
import type { Theme, Components } from '@mui/material/styles'
import { customShadows } from '@/theme/shadows'
import { GREY } from '@/theme/palette'

/** The base radius; a card doubles it, matching the reference application. */
export const BORDER_RADIUS = 8

export function componentOverrides(theme: Theme): Components<Theme> {
  return {
    MuiCssBaseline: {
      styleOverrides: {
        html: { WebkitFontSmoothing: 'antialiased', MozOsxFontSmoothing: 'grayscale' },
        '#root': { height: '100%' },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundImage: 'none' } },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          position: 'relative',
          boxShadow: customShadows.card,
          borderRadius: BORDER_RADIUS * 2,
          zIndex: 0,
        },
      },
    },
    MuiCardHeader: {
      defaultProps: {
        titleTypographyProps: { variant: 'h6' },
        subheaderTypographyProps: { variant: 'body2', marginTop: theme.spacing(0.5) },
      },
      styleOverrides: { root: { padding: theme.spacing(3, 3, 0) } },
    },
    MuiCardContent: {
      styleOverrides: { root: { padding: theme.spacing(3) } },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: BORDER_RADIUS },
        sizeLarge: { height: 48 },
        containedInherit: {
          color: theme.palette.common.white,
          backgroundColor: theme.palette.grey[800],
          '&:hover': { backgroundColor: theme.palette.grey[700] },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha(GREY[500], 0.2),
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: theme.palette.text.primary,
          },
        },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small' },
    },
    MuiDialog: {
      defaultProps: { fullWidth: true, maxWidth: 'sm' },
      styleOverrides: {
        paper: {
          boxShadow: customShadows.dialog,
          borderRadius: BORDER_RADIUS * 2,
          '&.MuiDialog-paperFullScreen': { borderRadius: 0 },
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: { root: { ...theme.typography.h6, padding: theme.spacing(3) } },
    },
    MuiDialogContent: {
      styleOverrides: { root: { borderTop: 0, borderBottom: 0 } },
    },
    MuiDialogActions: {
      styleOverrides: { root: { padding: theme.spacing(3) } },
    },
    MuiTabs: {
      defaultProps: { textColor: 'inherit', variant: 'scrollable' },
      styleOverrides: { scrollButtons: { width: 48, borderRadius: '50%' } },
    },
    MuiTab: {
      defaultProps: { disableRipple: true, iconPosition: 'start' },
      styleOverrides: {
        root: {
          padding: 0,
          opacity: 1,
          minWidth: 48,
          minHeight: 48,
          fontWeight: theme.typography.fontWeightMedium,
          '&:not(:last-of-type)': {
            marginRight: theme.spacing(3),
            [theme.breakpoints.up('sm')]: { marginRight: theme.spacing(5) },
          },
          '&:not(.Mui-selected)': { color: theme.palette.text.secondary },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          ...theme.typography.subtitle2,
          color: theme.palette.text.secondary,
          backgroundColor: theme.palette.background.neutral,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        standardInfo: {
          backgroundColor: alpha(theme.palette.info.main, 0.16),
          color: theme.palette.info.dark,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: { paper: { borderRight: `1px dashed ${theme.palette.divider}` } },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          boxShadow: theme.customShadows.dropdown,
          borderRadius: Number(theme.shape.borderRadius) * 1.5,
        },
      },
    },
    MuiLink: {
      defaultProps: { underline: 'hover' },
    },
  }
}
