/**
 * The single theme, assembled from the ported design tokens.
 *
 * `customShadows` is added to the theme object so a component can read
 * `theme.customShadows.card` instead of pasting a shadow string; the module
 * augmentation below is what makes that type-safe.
 */

import { createTheme, CssBaseline, ThemeProvider as MuiThemeProvider } from '@mui/material'
import { useMemo } from 'react'
import type { ReactNode } from 'react'
import '@fontsource/public-sans/400.css'
import '@fontsource/public-sans/500.css'
import '@fontsource/public-sans/600.css'
import '@fontsource/public-sans/700.css'
import '@fontsource/public-sans/800.css'
import { palette } from '@/theme/palette'
import { typography } from '@/theme/typography'
import { customShadows, shadows } from '@/theme/shadows'
import type { CustomShadows } from '@/theme/shadows'
import { BORDER_RADIUS, componentOverrides } from '@/theme/overrides'

declare module '@mui/material/styles' {
  interface Theme {
    customShadows: CustomShadows
  }
  interface ThemeOptions {
    customShadows?: CustomShadows
  }
}

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useMemo(() => {
    const base = createTheme({
      palette,
      typography,
      shadows: shadows as never,
      customShadows,
      shape: { borderRadius: BORDER_RADIUS },
    })
    return createTheme(base, { components: componentOverrides(base) })
  }, [])

  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </MuiThemeProvider>
  )
}
