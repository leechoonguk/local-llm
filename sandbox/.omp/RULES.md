# Sticky Rules

## Session Safety

Never modify `AGENTS.md` or any `.omp/` file without explicit user request.
Never commit or push unless the user explicitly asks.

## Harness Integrity

When modifying the harness (`.omp/` files, hooks, rules, MCP/LSP config), always reference OMP official documentation (`omp://`) first. The harness is the backbone of your development workflow — changes here affect every session. Read `omp://` docs (settings, hooks, rules, tools, SDK) to understand current behavior before touching anything. Never guess how the harness works; verify against the official guide.

## Workflow

Before creating or editing files in an area, read that area's rulebook entries
via `rule://<name>` — they are listed in the system prompt with their globs.
Discovering requirements up front is faster than rediscovering them one verify
failure at a time. When a verify failure names a rule area, read that rule
before retrying.

Keep the todo list stateful while debugging: after each verification run, record
which check is failing and the next single step — it is the task's memory across
context resets and compactions.

An additive task must not wipe existing code: prefer targeted edits over
full-file rewrites of existing files, and never truncate a file with `>`.
Never replace an existing import line with yours — add it alongside; existing
imports register models and behavior other code depends on.

Run the verification after wiring each layer or file group, not only at the
end — failures discovered early are cheaper than one pile at the finish.

Iterate with `make verify-fast` (add t="tests/..." to scope one file) — it skips
the coverage gate, so a fast pass never counts as done.

Before declaring work done, run the full `make verify` and confirm it is green.
