---
description: Rule conventions — how to write .omp/rules files, frontmatter, content structure, naming
globs:
      - .omp/rules/*.md
alwaysApply: false
---

# Rule File Conventions

## OMP Runtime Behavior

Rules load **dynamically** — never import them into `AGENTS.md`. OMP buckets
`.omp/rules/*.md` at session start:

| Bucket | OMP condition | Loading |
|---|---|---|
| Rulebook | `description` present; not accepted as TTSR; not always-apply | Name + `globs` + description listed in the system prompt; content read on demand via `rule://<name>` |
| Always-apply | `alwaysApply: true`; not accepted as TTSR | Full content injected into every session |
| TTSR | Accepted `condition` or `astCondition` | Activated only while the text/tool stream matches the trigger |

**TTSR globs trap**: on a TTSR rule, `globs` is a **runtime path gate** — the
match context must include at least one file path. `bash` tool calls never
carry file paths, so a globbed TTSR rule **never triggers on shell commands**
(`make migrate`, `alembic`, …). For workflow rules triggered by bash, omit
`globs` entirely and rely on `condition` alone.

**A rulebook entry delivers nothing but its description line.** `globs` are not
used to select rulebook content: editing a matching file injects no body, so a
rulebook rule is the *documentation* of an invariant that a hook enforces
mechanically. When an invariant must reach the model at the moment it is about
to be broken, that is a TTSR trigger — not a longer rulebook entry.

**Body size is a per-read tax, not a per-session one.** A rulebook body costs
nothing until something reads it, and then it costs all of it: measured over 87
sessions, guidance reads are **whole-file** (121 whole vs 12 paged), while the
254 paged reads were the author moving around a rule being edited. The whole
set of rules over 8 KB cost 214k tokens of guidance reads across those sessions
— **2.5k per session, 1.2% of a 200k window** — so splitting a long rule buys
little and costs a rulebook entry, a mapping row in `omp-hooks.md` and a deck
mention per new file. Split when one rule alone passes ~1k tokens per session
of guidance reads (today's worst, `omp-hooks.md` at 43 KB, is 0.93k); until
then, length is paid by whoever asks for it.

## TTSR Trigger Rules

A TTSR trigger is a small rule whose whole body is injected mid-stream, so it is
written to be read once, under interruption: state the construct, the
replacement, the enforcing hook, and `rule://<full-rule>` for the rest.

| Frontmatter | Required | Why |
|---|---|---|
| `condition` | yes | Regex, **quoted string** (a YAML list registers at runtime but reads as a rulebook rule to `check-omp-rules`, so the two disagree) |
| `scope` | yes | The default watches assistant prose and every tool argument — a code-token trigger would fire on *writing about* the token. Code triggers use `tool:edit(<glob>), tool:write(<glob>)`; a workflow trigger states `text, tool` on purpose |
| `interruptMode` | yes | Otherwise the machine-global default decides whether an edit is aborted |
| `globs` | no | Redundant once `scope` carries path globs, and fatal for bash-triggered rules (see the globs trap above) |

**Match the construct, not the word.** `# No session.begin() here` and
`no need for HTTPException in routers` are comments that exist to explain a ban;
an interrupting rule that fires on them is worse than no rule. Require the call,
the import, or the statement shape (`async with [\w.]*session\.begin\(`).

**Prove it before trusting it.** `omp ttsr test --source tool --tool edit --path
<file> '<snippet>'` must fire on the violating construct and stay quiet on the
comment, on the legal location, and on prose; `omp ttsr scan <dir>` must report
zero matches against the current tree, or every legitimate rewrite of those
lines interrupts a turn. AST conditions are **not** usable here: matching is
logged but delivery to the model is unreliable, and `repeatMode: once` then
suppresses the rule for the rest of the session.

**Register the trigger.** Add a mapping row in `omp-hooks.md` pointing at the
post hook that already owns the invariant. A trigger adds no validation domain:
it delivers early what the hook proves late.

## Project Rule File Policy

The following structure is repository governance layered over OMP's runtime;
OMP itself permits optional `globs` and does not require this exact layout.
`RULES.md` (top level of `.omp/`, not `rules/`) is this project's sticky rule;
do not duplicate it under `.omp/rules/`.


## Rule File Structure

Every rule file in `.omp/rules/` follows this exact format:

```
---
description: <short description>
globs:
      - <relative path patterns>
alwaysApply: false
---

# <Title>

<content sections follow>
```

### Frontmatter

| Field | Project requirement | Format | OMP runtime note |
|---|---|---|---|
| `description` | Yes | Sentence fragment | Required for rulebook visibility |
| `globs` | Yes for this repository's rulebook rules | Indented list | Optional metadata in OMP; runtime path gate only for TTSR |
| `alwaysApply` | Yes, set to `false` | `false` | OMP supports `true`; this repository reserves sticky guidance for `.omp/RULES.md` |

**Indentation:** globs use 6-space indent from the `globs:` line.

**Naming:** Frontmatter `description` value is matched against rule filenames. The file `backend-domain.md` has `description: Backend domain conventions — …`.

### Content Sections

Rules use Markdown with these section conventions:

| Section | Purpose | Pattern |
|---|---|---|
| `# <Title>` | Main topic | Matches rule name: `backend-domain.md` → `# Backend Domain` |
| `## Adding a New <Domain>` | How-to | Numbered steps or code blocks |
| `## <Topic> Conventions` | Rules | Bullet lists |
| `## Never Do These` | Anti-patterns | Negative bullet list |
| `## <Topic> Pattern` | Examples | Code blocks with language hint |

### Section Ordering

1. **Overview** — brief context (optional, inline after title)
2. **Conventions / Rules** — the actual rules (bulleted list)
3. **Pattern / Example** — code snippets or diagrams
4. **Adding a New …** — procedural how-to (numbered)
5. **Never Do These** — anti-patterns (negative bullets)

### Content Formats

- **Tables**: For API specs, Makefile targets, class schemas. Header: `| Header | Header |` → separator: `|---|---|`.
- **Code blocks**: With language (`bash`, `python`, `tsx`, `yaml`). Include path comments like `// frontend/src/App.tsx`.
- **Bullet lists**: Single-dash `- ` prefix. Sub-items use `- ` with no indent (flat lists).
- **Inline code**: Backtick-wrapped: `` `<name>` ``, `` `make dev` ``.

### Directory Naming

Prefix with the scope layer:

| Prefix | Scope | Examples |
|---|---|---|
| `backend-` | Backend only | `backend-domain.md`, `backend-migrations.md`, `backend-batch.md` |
| `frontend-` | Frontend only | `frontend-makefile.md`, `frontend-code-conventions.md` |
| `omp-` | Harness (.omp/) | `omp-conventions.md`, `omp-hooks.md`, `omp-ast-rules.md` |
| `root-` | Root / project-wide | `root-makefile.md` |
| *(none)* | Cross-cutting (spans root + backend) | `environment.md` — covers root `.env` (docker-compose) and `backend/.env` (Pydantic settings) |

**Cross-cutting exception:** a rule that spans multiple scopes (e.g. root +
backend) omits the prefix — same convention as pre-hooks (`strict-command-routing.ts`
omits `<scope>` when cross-cutting). `check-omp-rules.ts` allows prefix-less
filenames only for rules whose `globs` span more than one top-level directory.

## File Naming

- **lowercase**, hyphen-separated: `backend-domain.md`
- Description (frontmatter) maps to title in content: `backend-domain.md` → `# Backend Domain`
- New rules: create `.omp/rules/<scope>-<name>.md` — nothing else. The rulebook picks it up automatically; do **not** add any `@rules/` entry to `AGENTS.md`.
- Set `globs` to the paths the rule governs — they gate TTSR matching and are shown in the rulebook listing.
- Consider TTSR `condition` for rules that only matter during specific workflows (e.g. migration rules triggered by `alembic|migrat`).

## Never Do These

- Add rules outside `.omp/rules/` directory
- Import rules into `AGENTS.md` via `@rules/...` — rules load dynamically (rulebook + `rule://<name>`)
- Use `alwaysApply: true` — all rules use `false`; sticky needs belong in `RULES.md`
- Name a rule file `RULES.md` — it shadows the sticky `RULES.md`
- Skip `description` field — it must match the rule's scope
- Use 4-space indent for globs — use 6 spaces
- Merge unrelated topics into one rule file
- Write rules for code generated by a scaffold tool — the hook validates the pattern
- Forget to update `globs` when changing the rule's scope
