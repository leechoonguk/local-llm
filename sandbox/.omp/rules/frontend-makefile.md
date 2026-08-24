---
description: Frontend Makefile usage — targets, commands, and development workflow
globs:
      - frontend/Makefile
      - frontend/package.json
      - frontend/vite.config.ts
      - frontend/tsconfig.json
      - frontend/src/**/*.tsx
      - frontend/src/**/*.css
      - frontend/nginx.conf
alwaysApply: false
---

# Frontend Makefile Usage


## Self-Documenting Targets

Every target carries a `## <description>` on its header line. `make help` greps
those descriptions, so a target without one exists but cannot be found - and an
undiscoverable target is re-invented as a raw command. `check-makefiles`
enforces it on the root, backend, frontend and decks Makefiles.

## Makefile Targets

| Target | Command | Purpose |
|---|---|---|
| `make help` | `grep -E 'target:.*?## .*'` | Show this help |
| `make install` | `npm install` | Install frontend dependencies |
| `make dev` | `npx vite` | Vite dev server (:15173) |
| `make down` | `lsof -ti:15173` + `xargs kill -9` | Stop frontend (kill Vite) |
| `make verify` | `lint + typecheck + build` | Full quality gate (fail-fast) |
| `make lint` | `npx eslint .` | ESLint check |
| `make typecheck` | `npx tsc --noEmit` | TypeScript type check |
| `make build` | `tsc -b && vite build` | Production build |
| `make clean` | `rm -rf dist .vite node_modules/.vite *.tsbuildinfo` | Remove build, Vite, and TypeScript caches |

## Development Commands

1. **Start dev server**: `make dev` — Vite on :15173
2. **Stop dev server**: `make down` — kill Vite process on :15173
3. **Verify**: `make verify` — lint → typecheck → build (fail-fast)
4. **Build**: `make build` — production assets to `frontend/dist/`
5. **Install**: `make install` — install npm dependencies

## Project Structure

- `frontend/src/` — source files (`.tsx`, `.css`)
- `frontend/vite.config.ts` — Vite config (port 15173, `/api` proxy → :8000)
- `frontend/tsconfig.json` — TypeScript config (ES2022, strict, `@/*` alias)
- `frontend/package.json` — npm package config

## Code Conventions

Code conventions (React/TypeScript/Vite/ESLint/component pattern/API proxy) are
documented in `frontend-code-conventions.md` — that rule is the single source.
This rule only covers Makefile targets and the dev workflow.

## API Proxy

The `/api/*` → `http://localhost:18000` proxy (dev + nginx) is documented in
`frontend-code-conventions.md` — that rule is the single source.

In development: `make dev` starts Vite (:15173), `make down` stops it; proxy `/api` to backend.
In production: Nginx serves frontend and proxies `/api` to backend.

## Never Do These

- Forget `make verify` before commit (lint + typecheck + build)
