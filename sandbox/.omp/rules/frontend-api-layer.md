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

## An Identity Lookup Serves Its Own Answer

`placeholderData: (previous) => previous` belongs to a **list**: the table keeps
its rows while the next page loads. It does not belong to a read that answers
*which row is this* - a key lookup (`use…ByKey`), a detail (`…Keys.detail(id)`
with no window) - because the previous answer is a different row, and whatever
the screen does with the id it now does to the wrong one. Such a read is
`enabled`-gated too, so nothing is fetched while nothing is open and nothing is
left behind for the next key to inherit.

Measured on the 검사·조치 이력 list, which holds a product's (종류, 번호) and
needs its id: the lookup went through the list hook, so clicking a row opened
the dialog on the *previous* lookup's product - 886px of another company's
record, collapsing to 303px and replaced two frames later. The reader saw one
blink; whoever read that frame read the wrong product.

A tab's own paged list keyed under its record (`detail(`${id}:events`)`) is a
list and keeps its placeholder - `check-frontend-types` tells the two apart by
the window in the query.

## The One Verb Axios Cannot Serve

**A server-sent stream goes through `api.stream`, still inside
`lib/api/client.ts`.** XHR hands a response over only when it is complete, so
axios would deliver a whole turn's events in one lump after the last one -
which is a POST wearing a stream's clothes. `api.stream` is `fetch` with the
same bearer token and the same `ApiError` mapping; that is why the ban is on
raw `fetch` in a screen, not on `fetch` in the client.

It is the only verb with no response generic: a stream's frames are not one
model (`token`, `end`, `error`), so it yields `ServerSentEvent` and the
caller switches on the name. A chunk can split a frame and can carry three,
so the buffer keeps the remainder rather than assuming one chunk is one
frame, and the reader is cancelled in a `finally` - a caller that stops early
must not leave the socket open. `check-frontend-contract` reads
`api.stream(...)` as a POST on the endpoint it names, so a streaming route
still owes a caller and its constant still has to be used.

A stream has no cache: the screen reaches it through a hook that owns the
transcript and the request in flight (`useFoodChat`), not through `useQuery` -
there is nothing to invalidate, and the server keeps no conversation either.

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

`placeholderData` is load-bearing, not a nicety: without it `data` is
`undefined` during a fetch, so the grid loses its rows and its `rowCount` on
every page change and the footer blinks between "1–10 of 240" and nothing.

### A scope nothing invalidates is `REALTIME`

`invalidateQueries` is this application's only cache-refresh path — measured: no
`setQueryData`, `refetchQueries`, `removeQueries` or `resetQueries` exists in
`frontend/src`. So if no mutation names a scope, a non-zero `staleTime` is a
window in which the screen cannot show the truth and nothing on it can ask
again. The batch run log is the case: the scheduler writes those rows outside
HTTP, so a `STANDARD` window would report last night's failure as still running.

One-way. A scope that *is* invalidated may still choose `REALTIME` — `useUserList`
does, because it is read far more often than it is written, and that is a
judgement the check does not make.

**A child collection gets its own scope**, never a discriminator folded into the
parent's list key. Invalidation matches by prefix, so `batchKeys.list({scope:
'runs'})` sat under `batchKeys.lists()` and a schedule's own writes marked the run
log invalid — a containment the key claimed and the data does not have. It cost a
marking rather than a request only because `invalidateQueries` defaults to
`refetchType: 'active'` and that query is mounted only while its dialog is open;
the first screen that shows a run log beside a schedule write turns it into a
refetch. The split is also what makes the rule above computable at all: while the
runs lived under `batchKeys`, "is this scope invalidated" had no answer.

**Every declared scope is read by a query.** `authKeys` sat exported and
referenced by nothing — a scope with no reader is a screen that was never built,
or a key waiting to be copied onto the wrong collection.

### An action verb is a state request, and it invalidates nothing

Not machine-checked — whether a mutation *should* invalidate is domain
knowledge, and a check that guessed would either force a pointless refetch or
excuse a missing one. Stated because both instances got it right for the same
reason, and the next one should know it.

Some mutations change no row a screen displays:

| Hook | What it changes | Why no invalidation |
|---|---|---|
| `useRunBatch` | one execution | the grid shows `code`/`cron`/`enabled`, none of which a run touches; refetching would flicker for a state it does not draw |
| `useExecuteOperation` | nothing — it calls a provider | there is no cache entry: the result belongs to the inputs just typed, and a second identical call spends another upstream request |

**The verb pair is one endpoint carrying the wanted end state** (`{running:
true|false}`), not two endpoints and not a toggle. It mirrors the backend's own
split: `enabled` is activation — whether the clock starts the job — while
run/stop act on one execution and never touch the trigger. Collapsing them into
a single toggle would make "stop this run" silently unschedule a nightly job,
and a deactivated row could no longer be run by hand.

So the row carries both verbs as separate actions, and the toggle stays on
`enabled`, where it means what it says.

## Pagination Reality

The backend paginates with `offset`/`limit` and answers `Page<T>` — `items` plus
the collection's `total` (`app/schemas/page.py`), and no sort parameter
(`app/dependencies/query.py`). So:

- `useDataGridState` requests exactly `pageSize` rows and `rowCount` is the
  total the response carried. It used to ask for `pageSize + 1` and infer a next
  page from the extra row, which can say *more* but never *how many*: the footer
  read `1–10` until the last page.
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
