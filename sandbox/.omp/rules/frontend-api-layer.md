---
description: Frontend API layer — one axios client, services, query keys, cache policy, invalidation
globs:
      - frontend/src/lib/api/**/*.ts
      - frontend/src/types/api.ts
alwaysApply: false
---

# Frontend API Layer

Three responsibilities, three layers, and nothing shared between them: the
client owns the transport, a service owns one endpoint each, a hook owns the
cache. A screen that reaches past any of them loses what that layer guarantees.

Machine-checked by `check-frontend-api-layer.ts`
(`make check-frontend-api-layer`) plus `ast-grep/rules/frontend-api/`.

## One Client

`lib/api/client.ts` is the only file that may build a client or call the
platform. It is the only place that:

- attaches the bearer token to the request
- turns a 401 into a cleared session and one `auth:session-expired` event
- converts every failure into `ApiError` (`detail` / `code` / `request_id`)

A second `axios.create` or a raw `fetch` skips all three, and the failure is
invisible: the request still works, the session handling does not.

## Services

```ts
export const userService = {
  list: (params: OffsetLimitParams) => api.get<User[]>(USER_ENDPOINTS.LIST, { params }),
  remove: (id: string) => api.delete<OkResponse>(USER_ENDPOINTS.DELETE(id)),
}
```

- One function per endpoint, named for the verb, not the screen.
- No `useQuery` / `useMutation` — a service that caches cannot be reused.
- No URL literal: the path comes from `endpoints.ts`. Two files are exempt and
  the check knows it — `routes/paths.ts` holds **browser** routes (owned by
  `frontend-routing.md`), and `client.ts` names the auth paths its 401 handler
  must not retry.

## Hooks

| Concern | Rule |
|---|---|
| Key | from the `*Keys` factory — never a `queryKey: [...]` literal |
| Staleness | `staleTime: QUERY_STALE_TIME.<NAME>` — a bare number says how long, never why |
| Paging | a `use*List` hook declares `placeholderData: (previous) => previous` |
| Invalidation | `useCreate*` / `useUpdate*` / `useDelete*` invalidate the list key |

`placeholderData` is load-bearing, not a nicety: `usePagedRows` derives
`hasNextPage` from the page it holds, and MUI resets the page to zero when
`paginationMeta` goes back to `undefined`. Losing the placeholder makes paging
jump to the first page mid-fetch.

## Pagination Reality

The backend paginates with `offset`/`limit` and returns a **bare array** — no
envelope, no total, no sort parameter (`app/dependencies/query.py`). So:

- `useDataGridState` requests `pageSize + 1` rows and the extra row is the only
  evidence of a next page
- there is no search box and no server sort, because there is no parameter to
  send. A control the API cannot honour is a lie in the UI.

## Review Judgement (not machine-checked)

- Whether a `staleTime` constant is the *right* one for the data. The check sees
  that a named constant was used, never that `LONG` suits a collection someone
  edits hourly.
- Whether a mutation should also invalidate a **sibling** domain's key. Only the
  domain's own list key is required, because that is the one the check can
  derive; a cross-domain effect is a decision.
- Whether a service function belongs at all — a service with one caller and a
  screen-shaped name is a screen leaking into the transport layer.

## Never Do These

- Call `axios.create` or `fetch` outside `lib/api/client.ts`
- Import `axios` outside the client and its error mapper
- Write a backend path literal outside `endpoints.ts`
- Put `useQuery` in a service, or `apiClient` in a hook
- Import a service from a screen — go through the hooks layer
- Write a mutation that changes a collection without invalidating its list key
