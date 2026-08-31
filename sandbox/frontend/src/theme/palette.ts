/**
 * The palette, ported verbatim from the reference application.
 *
 * These are exact values, not approximations: the greys carry the surface
 * hierarchy (`background.neutral` is GREY[200], which every table header and
 * dialog body uses), and `lighter`/`darker` on each colour is what the soft
 * `Label` variant reads. A colour picked in a component instead of here has no
 * dark-mode counterpart and no soft variant.
 */

import { alpha } from '@mui/material/styles'

declare module '@mui/material/styles' {
  interface TypeBackground {
    neutral: string
  }
  interface SimplePaletteColorOptions {
    lighter: string
    darker: string
  }
  interface PaletteColor {
    lighter: string
    darker: string
  }
}

export const GREY = {
  0: '#FFFFFF',
  100: '#F9FAFB',
  200: '#F4F6F8',
  300: '#DFE3E8',
  400: '#C4CDD5',
  500: '#919EAB',
  600: '#637381',
  700: '#454F5B',
  800: '#212B36',
  900: '#161C24',
}

const PRIMARY = {
  lighter: '#C8FACD',
  light: '#5BE584',
  main: '#00AB55',
  dark: '#007B55',
  darker: '#005249',
  contrastText: '#FFFFFF',
}

const SECONDARY = {
  lighter: '#D6E4FF',
  light: '#84A9FF',
  main: '#3366FF',
  dark: '#1939B7',
  darker: '#091A7A',
  contrastText: '#FFFFFF',
}

const INFO = {
  lighter: '#CAFDF5',
  light: '#61F3F3',
  main: '#00B8D9',
  dark: '#006C9C',
  darker: '#003768',
  contrastText: '#FFFFFF',
}

const SUCCESS = {
  lighter: '#D8FBDE',
  light: '#86E8AB',
  main: '#36B37E',
  dark: '#1B806A',
  darker: '#0A5554',
  contrastText: '#FFFFFF',
}

const WARNING = {
  lighter: '#FFF5CC',
  light: '#FFD666',
  main: '#FFAB00',
  dark: '#B76E00',
  darker: '#7A4100',
  contrastText: GREY[800],
}

const ERROR = {
  lighter: '#FEE2E2',
  light: '#FCA5A5',
  main: '#EF4444',
  dark: '#DC2626',
  darker: '#991B1B',
  contrastText: '#FFFFFF',
}

export const palette = {
  common: { black: '#000000', white: '#FFFFFF' },
  primary: PRIMARY,
  secondary: SECONDARY,
  info: INFO,
  success: SUCCESS,
  warning: WARNING,
  error: ERROR,
  grey: GREY,
  divider: alpha(GREY[500], 0.24),
  text: {
    primary: GREY[800],
    secondary: GREY[600],
    disabled: GREY[500],
  },
  background: { paper: '#FFFFFF', default: '#FFFFFF', neutral: GREY[200] },
  action: {
    active: GREY[600],
    hover: alpha(GREY[500], 0.08),
    selected: alpha(GREY[500], 0.16),
    disabled: alpha(GREY[500], 0.8),
    disabledBackground: alpha(GREY[500], 0.24),
    focus: alpha(GREY[500], 0.24),
    hoverOpacity: 0.08,
    disabledOpacity: 0.48,
  },
}
