---
description: Backend router parameters — path/body/dependency/query kinds, UUID ids, pagination aliases, signature order
globs:
      - backend/app/routers/*.py
      - backend/app/dependencies/query.py
alwaysApply: false
---

# Backend Router Parameters

An endpoint's signature is its contract with every caller and with OpenAPI. Each
parameter is exactly one of four kinds, and each kind has one spelling — so a
reader knows what identifies the resource, what it accepts, and what is wiring,
without reading the body.

Machine-checked by `check-backend-router-params.ts`; the "no inline call"
half is an AST rule (`ast-grep/rules/router/inline-depends.yml`).

## The Four Kinds

| Kind | Spelling | Example |
|---|---|---|
| **Path** | declared in the route template, no default | `batch_id: UUID` |
| **Body** | one `*Request` schema named `data`, writes only | `data: BatchCreateRequest` |
| **Dependency** | `Annotated` alias ending in `Dep`, from `app/dependencies/` | `user_service: UserServiceDep`, `current_user: CurrentUserDep` |
| **Query** | `Annotated` alias ending in `Query`, from `app/dependencies/query.py` | `offset: OffsetQuery = 0` |

A parameter that fits none of the four is a bare primitive: no bound, no
OpenAPI constraint, no reuse. It is a violation, not a shortcut.

## Signature Order

```text
path → body → dependencies → query (with defaults)
```

What identifies the resource comes first, then what the caller sends, then the
wiring, then the optional knobs. Python already forces defaults last; the rest is
so every endpoint reads the same.

## Path Parameters

- **Every `{name}` in the route template is a signature parameter with the same
  name.** A mismatch is not a type error: FastAPI turns the unknown name into a
  *required query parameter*, so every call answers 422 and the path segment is
  ignored.
- **Ids are `UUID`** (`batch_id: UUID`) — a malformed id fails at the boundary
  instead of reaching the database. Natural keys stay `str`
  (`secret_name: str`, `operation_code: str`).
- **No defaults.** A path segment that can be omitted is a different route.

## Body

- Writes (`POST`/`PUT`/`PATCH`) take **exactly one** `*Request` schema named
  `data`. Two body parameters make FastAPI embed each under its own key, which
  silently changes the wire format.
- A form-based endpoint (`POST /auth/login` → `OAuth2FormDep`) is the documented
  exception: the form dependency *is* the body.
- **`GET` and `DELETE` take no body.** Proxies, caches and some clients drop it,
  so an endpoint whose semantics depend on it fails only in production.

## Query and Pagination

- Bounds are declared **once**, in `app/dependencies/query.py`:

  ```python
  OffsetQuery = Annotated[int, Query(ge=0)]
  LimitQuery = Annotated[int, Query(ge=1, le=100)]
  ```

- Defaults are set at the call site, never inside `Annotated`, and they are the
  same two values in **every** list endpoint:

  ```python
  offset: OffsetQuery = 0,
  limit: LimitQuery = settings.items_per_user,
  ```

- **A collection read answers `Page[...]`, never a bare `list[...]`.** The
  envelope carries `items` and `total` (`app/schemas/page.py`), so a client can
  say "1–10 of 240" on the first page instead of learning the number on the
  last. An array can only be probed — ask for one row more than fits and infer
  "there is another page" — which is not a count.
- **Every collection read is paginated — no exceptions.** A
  sub-collection (`GET /{integration_id}/secrets`) is a collection: "the foreign
  key keeps it small" is an assumption about data, not a bound in the code, and
  it stops being true in production. Symmetry is the point: a caller pages the
  same way everywhere, and a reviewer never has to ask which endpoints are
  special.
- **The page size has one source: `settings.items_per_user`.** A literal default
  (`limit: LimitQuery = 100`) is a second page size that no environment can
  change and that drifts from the rest of the API.
- **`ITEMS_PER_USER` ≤ the `le=` cap.** It is the default of every list
  endpoint, so a configured page size above the cap makes every unpaginated call
  answer 422. Checked against both `.env` files.
- Pagination flows through the layers unchanged: router
  (`offset`/`limit` aliases) → service (`offset: int = 0, limit: int = 100`) →
  repository (`.offset(offset).limit(limit)`). A router that accepts pagination
  and drops it before the query is worse than none: the caller is told it worked.
- Routers never declare their own `Annotated` alias, and never call `Query()`,
  `Depends()`, `Path()`, `Body()` or `Header()` inline — the alias is the single
  place a parameter's validation lives.

## Never Do These

- Name a path parameter in the route template but not in the signature
- Type an id path parameter as `str` or `int`
- Give a path parameter a default
- Accept `dict`, `Any`, or a bare `int`/`str` query parameter instead of an alias
- Take two body parameters, or name the body anything but `data`
- Put a body on `GET`/`DELETE`
- Ship any `Page[...]` endpoint without `offset`/`limit`, sub-collection included
- Return a bare `list[...]` from a read — the total is part of the answer
- Default `limit` to a literal instead of `settings.items_per_user`
- Accept `offset`/`limit` in a router and not pass them to the query
- Raise `ITEMS_PER_USER` above the `LimitQuery` cap
- Declare a pagination alias inside a router, or call `Query()` inline
