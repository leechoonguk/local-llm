---
description: Frontend code conventions — React, TypeScript, Vite, ESLint, file structure
globs:
      - frontend/package.json
      - frontend/vite.config.ts
      - frontend/tsconfig.json
      - frontend/src/**/*.tsx
      - frontend/src/**/*.css
alwaysApply: false
---

# Frontend Code Conventions

## React

- **React 19**, functional components only (no class components)
- `createRoot` from `react-dom/client` (React 18 `render` deprecated)
- `StrictMode` wrapper in entry point (`main.tsx`)

## TypeScript

- **TypeScript 5.9**, `strict: true`, `verbatimModuleSyntax: true`
- Target: **ES2022**
- Module: **ESNext**
- Resolution: **bundler**
- `noUnusedLocals: true`, `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- `noUncheckedSideEffectImports: true`

## Vite

- **Vite 8**, `@vitejs/plugin-react`
- Port: **15173** (dev server)
- `@/*` alias resolves to `./src/`
- Dev proxy: `/api/*` → `http://localhost:18000/*` (strips `/api` prefix)

## ESLint

- **ESLint 10**, `typescript-eslint`
- `eslint-plugin-react-hooks` — `rules-of-hooks` enforced
- `@eslint/js` — basic JS rules

## File Structure

```
frontend/
  src/
    main.tsx          # Entry point — createRoot, StrictMode
    App.tsx           # Root component
    styles.css        # Global styles
    vite-env.d.ts     # Vite type declarations
  vite.config.ts      # Vite config
  tsconfig.json       # TypeScript config
  package.json        # npm package
```

## Component Pattern

```tsx
export default function App() {
    const [state, setState] = useState<Type | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
      fetch('/api/endpoint')
           .then(res => {
               if (!res.ok) throw new Error(`HTTP ${res.status}`)
               return res.json() as Promise<Type>
           })
           .then(setState)
           .catch(setError)
     }, [])

    return (
       <main>
           {/* content */}
       </main>
     )
}
```

Rules:
- Functional components, default export
- `useState` for local state, `useEffect` for side effects
- `fetch` for API calls — no external HTTP libraries
- Type safety: explicit types on state, props, API responses
- Semantic HTML: `<main>`, `<dl>`, `<dt>`, `<dd>`, `<p>`, `<h1>`

## File Naming

| Type | Convention | Example |
|---|---|---|
| Component | PascalCase | `App.tsx`, `Feature.tsx` |
| Styles | lowercase | `styles.css` |
| Entry | lowercase | `main.tsx` |
| Types | PascalCase | `types.ts` |

## Styling

- **CSS only** (no CSS-in-JS, no Tailwind)
- `system-ui` font family, `light-dark` color scheme
- Semantic HTML with `<dl>` / `<dt>` / `<dd>` for data grids
- `max-width: 40rem`, `margin: 2rem auto` for content container
- `padding: 0 1rem` for mobile responsiveness

## API Interaction

- Frontend proxies `/api/*` to backend `http://localhost:18000`
- Example: `GET /api/items` → backend `GET /items` (on port 8000)
- Response: `res.json() as Promise<Type>` for typed responses
- Error: catch branch sets error state

## Review Judgement (not machine-checked)

- A package installed without being added to `package.json` - the check cannot
  see `node_modules` state, only what the manifest declares.

## Never Do These

- Use class components — functional only
- Import files without `@/` alias when in `src/`
- Hardcode port numbers in components — use Vite config
- Add npm packages without updating `package.json`
- Forget `make verify` before commit (lint + typecheck + build)
- Use `fetch` without checking `res.ok`
