---
description: Frontend routing — path registry, route table, navigation model, layout guards
globs:
      - frontend/src/App.tsx
      - frontend/src/routes/paths.ts
      - frontend/src/layouts/**/*.tsx
      - frontend/src/auth/*.tsx
alwaysApply: false
---

# Frontend Routing

Three tables describe the same set of screens, and all three are generated from
one: the registry names the paths, the route table binds them to components, the
navigation model makes them reachable. When they disagree the failure is silent —
a dead link, or a screen nobody can find.

Machine-checked by `check-frontend-routing.ts` (`make check-frontend-routing`).

## The Three Tables

| File | Role |
|---|---|
| `routes/paths.ts` | `PATHS` — every path, named once |
| `App.tsx` | `<Route path={PATHS.x} element={<XPage />} />` |
| `layouts/dashboard/config-navigation.tsx` | `NAV_ITEMS` — the sidebar |

Both directions are checked: a registry leaf that is not routed is a path that
reaches nothing; a route or nav entry not in the registry is a literal waiting
to break. `PATHS.root` and `PATHS.auth.login` are the two documented
non-navigation leaves — the root only redirects, and login sits outside the
authenticated shell.

## Guards Belong to Layouts

```tsx
<Route path={PATHS.auth.login} element={<AuthLayout />}>   {/* GuestGuard */}
<Route element={<DashboardLayout />}>                      {/* AuthGuard  */}
```

A guard inside a page protects that page and nothing else, so the next page
added beside it is unprotected with no diff to notice. `AuthGuard` lives in
`DashboardLayout`, `GuestGuard` in `AuthLayout`, and a page that guards itself
is a violation.

`AuthGuard` distinguishes three states, not two: *initialising* (a token exists
and `GET /auth/me` has not answered), *authenticated*, and *anonymous*. A guard
that treats the first as the third signs the user out on every reload.

## Code Splitting

Pages are `lazy()` and the route table is wrapped in one `Suspense`. MUI and the
data grid are most of the bundle; a user who only signs in should not download
the provider-configuration screen to do it.

## Review Judgement (not machine-checked)

- Whether a route belongs in the sidebar at all, or under a group that is not
  the one it was put in. Presence is checked; placement is a decision.
- Whether a redirect target is the right one after login.
- Whether a path reads as a URL a user could type.

## Never Do These

- Write a literal path in `to=`, `navigate(...)` or `path=` — use `PATHS`
- Route a screen without adding it to `NAV_ITEMS` (except the documented two)
- Put `AuthGuard` or `GuestGuard` inside a page
- Add a path to the registry and leave it unrouted
- Redirect from a guard without carrying the attempted path
