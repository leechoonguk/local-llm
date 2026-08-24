# Sticky Rules

## Session Safety

Never modify `AGENTS.md` or any `.omp/` file without explicit user request.
Never commit or push unless the user explicitly asks.

## Harness Integrity

When modifying the harness (`.omp/` files, hooks, rules, MCP/LSP config), always reference OMP official documentation (`omp://`) first. The harness is the backbone of your development workflow — changes here affect every session. Read `omp://` docs (settings, hooks, rules, tools, SDK) to understand current behavior before touching anything. Never guess how the harness works; verify against the official guide.
