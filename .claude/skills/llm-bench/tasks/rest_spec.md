# Domain spec — 공지사항 (notice)

This is the requirement, not the implementation. The repository's own conventions
decide how it is built; read `.omp/rules/backend-domain.md` and copy the sibling.

## Resource

A notice is an announcement an operator publishes. It is owned by the system, not
by an end user, so there is no per-user scoping.

| Field | Type | Rules |
|---|---|---|
| `title` | string | required, 1–200 characters, searchable |
| `content` | string | required, long text, no length cap |
| `pinned` | boolean | required, defaults to `false` — pinned notices sort first |
| `published_at` | timestamp with timezone | optional; `null` means drafted but not published |

Identity, auditing and optimistic locking follow whatever the existing domains
already use — do not invent a second convention for them.

## Behaviour

- Create, read one, list, update, delete.
- Listing is paginated with the same query convention every other list endpoint
  in this repository uses, and returns pinned notices before unpinned ones.
- Reading a notice that does not exist is a 404 through the repository's own
  domain exception layer, never a bare `HTTPException` raised in the service.
- Every endpoint requires an authenticated caller, using the dependency the
  existing routers already use. Do not add a new authentication mechanism.
- `title` is unique. Creating a second notice with an existing title is a 409.

## Out of scope

- No external HTTP calls, no cache, no background job, no file upload.
- No frontend work.
