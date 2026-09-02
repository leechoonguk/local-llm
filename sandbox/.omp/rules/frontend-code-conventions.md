---
description: Frontend code conventions — React, TypeScript, Vite, MUI, ESLint, file structure
globs:
      - frontend/package.json
      - frontend/vite.config.ts
      - frontend/tsconfig.json
      - frontend/src/**/*.tsx
      - frontend/src/**/*.ts
      - frontend/src/**/*.css
alwaysApply: false
---

# Frontend Code Conventions

Machine-checked by `check-frontend-code.ts` (`make check-frontend-code`) for the
structural half; the toolchain (`make verify` → lint, typecheck, build) owns the
rest.

## Stack

| Concern | Choice |
|---|---|
| Framework | React 19, functional components only |
| Language | TypeScript 5.9, `strict`, `verbatimModuleSyntax`, `noUnusedLocals` |
| Build | Vite (dev server 25173, `/api` proxied to `localhost:28000`) |
| UI | MUI 7 + Emotion, `@mui/x-data-grid` 8 |
| Server state | TanStack Query 5 |
| Forms | react-hook-form 7 + yup via `@hookform/resolvers` |
| HTTP | axios (one instance, `lib/api/client.ts`) |
| Routing | react-router 7 (`BrowserRouter`) |
| i18n | i18next + react-i18next (ko default, en) |
| Notifications | notistack, through `useToast` |
| Icons | `@iconify/react`, through `components/iconify` |

A package used in `src/` must be declared in `package.json`: the check cannot see
`node_modules`, only what the manifest claims.

## File Structure

```
frontend/src/
  main.tsx                  entry — createRoot, StrictMode, Router, Providers
  App.tsx                   route table
  config.ts                 API base, timeouts, page sizes
  styles.css                the only stylesheet
  types/                    wire types (one file per domain + api.ts)
  lib/api/                  client, endpoints, queryKeys, queryDefaults,
                            services/, hooks/
  auth/                     AuthContext, guards
  hooks/                    useDataGridState, useServerTablePage, useCrudDialog, useToast
  components/               presentational building blocks, one directory each
  layouts/                  dashboard shell + auth shell
  sections/<domain>/        screens
  pages/                    route components
  routes/paths.ts           path registry
  locales/                  ko.ts, en.ts, i18n.ts
  theme/                    the single MUI theme
  utils/                    pure helpers
```

## Components

- One component per file, `export default function <Name>`, file named `<Name>.tsx`
- Props as a named `interface <Name>Props` (inline for one or two props)
- No `React.FC`, no class components
- Imports through the `@/` alias — a relative import breaks when the file moves
- `sx` for layout, the theme for appearance: a repeated `sx` is a theme default
  that has not been written yet
- Constants (widths, page sizes, cycles) after the imports, `UPPER_SNAKE_CASE`,
  never inline magic numbers in JSX

## Styling

- `styles.css` carries only the document reset; everything else is MUI
- No CSS modules, no Tailwind, no styled-components: two styling systems means
  two answers to "where does this colour come from"
- Colours and radii come from the theme, never a literal in a component

## Review Judgement (not machine-checked)

- Whether a `sx` block should have become a theme default
- Whether a component with six props should have been two components
- Whether a copied screen should have diverged as much as it did

## Never Do These

- Use a class component
- Import with a relative path inside `src/`
- Hardcode a port or a host in a component — the proxy owns that
- Add an npm package without adding it to `package.json`
- Introduce a second styling system
- Name a file differently from the component it default-exports
