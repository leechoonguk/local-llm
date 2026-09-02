---
description: AST rule authoring — ast-grep rule YAML conventions, pattern syntax, pitfalls
globs:
      - .omp/ast-grep/**/*.yml
      - .omp/sgconfig.yml
alwaysApply: false
---

# AST Rules

## Purpose

Structural code checks that string matching cannot express precisely — function
signatures, async-ness, naming conventions, parameter types — are written as
**ast-grep rules** in `.omp/ast-grep/rules/<scope>/` and executed by post hooks via
the shared runner `.omp/hooks/lib/ast-rules.ts` (`runAstRules`).

This rule covers **how to write ast-grep rules**. The hook-side contract (which
hook runs which rule dir, `expect: present` semantics) lives in `omp-hooks.md`
"AST Rule Contract".

**Project governance:** the directory layout and 3-way sync below are this
repository's ast-grep policy. OMP does not require AST rules or a rule↔hook
mapping.

## Directory Structure

The structural rule set lives under **one parent**, `.omp/ast-grep/`, in
ast-grep's own documented project layout: the rules and the cases that prove
them are siblings, never mixed. They cannot share a directory — `ruleDirs`
parses every `.yml` it finds and a test case has no `language:`/`rule:` key, so
colocation fails the whole scan (measured: `Cannot parse rule … missing field
language`).

```
.omp/ast-grep/
+-- rules/        # ruleDirs — one directory per path scope
+-- tests/        # testDir — <scope>-<rule>-test.yml, one per rule
```

```
.omp/ast-grep/rules/
+-- domain/       # 5-layer CRUD structure checks — run by check-backend-domain.ts
| +-- service-method-async.yml
| +-- repository-method-uuid-param.yml
| +-- service-transaction-write-only.yml
+-- router/       # router checks — run by check-backend-domain.ts (scans routers/)
| +-- write-auth.yml
| +-- inline-depends.yml
| +-- response-model.yml
| +-- auth-all.yml
+-- model/        # SQLAlchemy model structural checks — run by check-backend-domain.ts
| +-- id-standard.yml
| +-- field-mapped-pattern.yml
+-- transaction/  # transaction management checks — run by check-backend-domain.ts
| +-- service-only.yml
+-- service/      # service layer checks — run by check-backend-auth.ts
| +-- repository-param.yml
+-- exceptions/  # raise-shape checks — run by check-backend-exceptions.ts
| +-- builtin-forbidden.yml
| +-- http-exception-forbidden.yml
| +-- instance-raise.yml
+-- naming/       # code-wide naming/encapsulation checks — run by check-backend-naming.ts
| +-- var-name.yml
| +-- repository-access.yml
| +-- inner-function-underscore.yml
+-- conventions/  # auth-specific conventions — run by check-backend-auth.ts
| +-- current-user-router-only.yml
+-- batch/        # batch job checks — run by check-backend-batch.ts
| +-- job-async.yml
| +-- service-constructor.yml
| +-- session-from-engine.yml
+-- environment/  # env hardcoding checks — run by check-environment.ts
  +-- os-environ-direct.yml
  +-- hardcoded-connection.yml
  +-- hardcoded-port.yml
```

- One scope directory per post hook that uses `runAstRules`
- `check-omp-hooks.ts` verifies: every rule YAML is referenced by exactly one
  hook, every `runAstRules` user references ≥1 rule dir

## Scope Equals The Claim

A rule asserts one property. What it *matches* must be that property and
nothing else — an accidental second condition rides along invisibly, and the
day it binds, the rule decides something nobody chose. Four measured cases from
this repository, all the same defect:

| Rule | Claim | What the pattern also demanded | What it decided |
|---|---|---|---|
| `repository-method-uuid-param` | the id parameter is `UUID` | the signature fits on one line (`\(self, ` with a literal space) | a table's name, chosen to keep the line under 100 columns |
| `service-transaction-write-only` | a transaction opens only in a write method | the method name starts with a letter (no `_`) | a private helper had to stay public |
| `service-method-async` | nothing sync may touch the session | *where* the function sat, not what it touched: first every `def` in the layer, then only methods | pure helpers were pushed out of `services/` into `schemas/`; then a sync module function could hold a session beside them |
| `check-code-layout` member order | class members run config → fields → … | docstring prose (`derived: …` read as a field) | a sentence had to be reworded to satisfy a layout rule |

Each was found by a human noticing a decision that made no sense, never by a
gate. The counter-measures are cheap and belong in the pattern:

- **Anchor on structure, not on whitespace.** `\s*` between tokens, and
  `inside: { kind: class_definition, stopBy: end }` when the claim is about
  methods. A formatter must never be able to turn a rule red.
- **Say which construct.** A regex over `function_definition` matches methods
  and module functions alike; if the claim names one, the rule must too.
- **Prose is not code.** A scanner that reads a file line by line owes string
  and comment state the same tracking it gives brackets.
- **Prove both sides.** The case file carries a `valid:` snippet that differs
  from the `invalid:` one *only* in the asserted property — a wrapped
  signature, a private write helper, a module-level function. That is what
  makes the extra condition visible before it ships.

## Ownership: One Invariant, One Owner

An AST rule and a TS regex asserting the same thing drift apart the moment one
is edited — and the weaker one (the regex) is what keeps being trusted, because
it never needed ast-grep to run. So each invariant has exactly one owner:

| Kind of claim | Owner | Example |
|---|---|---|
| Shape of code inside one file | **AST rule** | no `raise HTTPException`, `session.begin()` outside services, non-async service method |
| Two files at once, non-Python surfaces, numbers, sets, ordering, runtime | **TS lib** | class ↔ handler sync, router ↔ `.http`, Makefile ↔ docs, `ITEMS_PER_USER ≤ le=`, banner order |

**Declared, not inferred.** A rule lists the literals it owns:

```yaml
owns:
  - "asyncio.create_task"
```

`check-omp-hooks` then rejects any post hook whose **regex** matches a declared
token (comments and messages may name it — they point at the owner). Inference
was tried and dropped: a hook naming `created_by` to require the audit endpoint
to *expose* it is a different claim from a rule requiring a *comparison* with it.

## Proof: Every Rule Has a Failing Case

A rule is a claim, and an unexercised claim is decoration: an anchored regex, a
wrong `kind`, or a `$$$ARGS` arity mistake matches **nothing** and the check
stays green forever. So every rule carries cases, and `make check-ast-rules`
runs them:

- `.omp/sgconfig.yml` declares `ruleDirs: [ast-grep/rules]` and
  `testConfigs: [{ testDir: ast-grep/tests }]`
- `.omp/ast-grep/tests/<scope>-<rule>-test.yml` holds `id:` plus `valid:`
  (must **not** match) and `invalid:` (must match) snippets
- `ast-grep test` is the checker; `check-ast-rules` additionally requires a case
  file per rule, so a new rule cannot ship unproven

For an `expect: present` rule the semantics invert (a match is the required
shape), so its `invalid:` list holds the **compliant** snippet. Each such test
file states that in a header comment.

**ast-grep is a hard dependency.** `runAstRules` used to return `[]` when the
binary was missing — every structural rule silently vanished and `make verify`
printed PASS. It now reports that as an issue, per rule directory: silence is
never a pass.

## 3-Way Sync Contract

Rule files, hook wiring, and docs must stay in sync. `check-omp-hooks.ts`
verifies all three directions mechanically:

| Direction | Source of truth | Verified |
|---|---|---|
| **Docs ↔ disk** | `omp-hooks.md` "AST Rule Contract" table + each domain rule's "Validation (Post-Hook)" table | every file listed in a doc exists on disk (no stale names); every file on disk is listed in a doc (no orphans) |
| **Hook ↔ disk** | `runAstRules` calls in post hooks | every rule dir is referenced by exactly one hook; every `runAstRules` user references ≥1 dir |
| **Naming** | `omp-ast-rules.md` "Naming Conventions" | `<subject>-<property>.yml`, no scope prefix/abbreviation |

**Workflow when changing a rule:**

1. Create/rename/delete the rule YAML in `.omp/ast-grep/rules/<scope>/`
2. Update the matching rows in `omp-hooks.md` "AST Rule Contract" **and** the
   domain rule's "Validation (Post-Hook)" table
3. Run `make verify` — `check-omp-hooks` flags any direction that drifted

A rename without the doc update is caught as a stale reference; a new rule
without a doc row is caught as an orphan.

## Naming Conventions

### Directory: `<scope>` (lowercase, singular)

The directory name is the **scope** — the layer or concern the rules validate.
It must match the hook's domain: `domain/`, `batch/`, `environment/`.

### File: `<subject>-<property>.yml` (lowercase, hyphen-separated)

The filename describes **what the rule checks**, without repeating the scope:

| Pattern | Example | Meaning |
|---|---|---|
| `<subject>-<property>` | `service-method-async.yml` | nothing sync touches the session |
| | `repository-method-uuid-param.yml` | repository methods take UUID params |
| | `job-async.yml` | batch jobs must be async |
| | `service-constructor.yml` | batch must construct Service(session) |
| | `os-environ-direct.yml` | no direct os.environ access |
| | `hardcoded-connection.yml` | no hardcoded connection strings |
| | `hardcoded-port.yml` | no hardcoded service ports |

Rules:

- **No scope prefix in filenames** — the directory already carries the scope.
  `batch/batch-job-async.yml` is wrong (scope duplicated); use `batch/job-async.yml`.
- **No abbreviations** — `env-` is wrong for the `environment/` scope; the
  directory name is the full scope.
- Lowercase, hyphen-separated, no underscores.
- `id` in the YAML frontmatter matches the filename (minus `.yml`).

## Rule Semantics

| Type | Declaration | Match meaning |
|---|---|---|
| **Negative** (default) | no `expect` field | a match is a **violation** |
| **Positive** | `expect: present` (top-level, alongside `id`/`language`) | **absence** of any match is the violation |

Positive rules fit "must contain this" checks (e.g. `Service(session)` call);
negative rules fit "must not look like this" checks (e.g. non-async method).

## Rule YAML Format

```yaml
id: service-method-async
language: python
rule:
  kind: function_definition
  regex: "^def \\w+\\("
  not:
    any:
      - regex: "^async def \\w+\\("
      - regex: "^def __init__\\("
message: "service method must be async (only __init__ may be sync)"
```

Rules execute as: `ast-grep scan --rule <file> <paths> --json --include-metadata`.
The `message` field surfaces in the hook warning. For negative rules, each match
becomes one issue; for positive rules, zero matches becomes one issue per path
group.

## Building Blocks

### Atomic rules

| Rule | Use |
|---|---|
| `pattern` | AST pattern with metavariables (`$NAME`, `$$$ARGS`). Matches one AST node. |
| `kind` | Node kind (e.g. `function_definition`, `call`). Use the ast-grep playground to look up kinds. |
| `regex` | Rust regex matched against the **whole** node text. |

### Composite rules

| Rule | Use |
|---|---|
| `all: [...]` | all sub-rules must match |
| `any: [...]` | any sub-rule must match |
| `not: <rule>` | single sub-rule must **not** match |
| `constraints: { $VAR: { regex: ... } }` | filter matches by metavariable content — **top-level**, next to `rule:` |

### Relational rules

| Rule | Use |
|---|---|
| `has: { field: ..., pattern: ... }` | target has a descendant matching the sub-rule |
| `inside: { pattern: ... }` | target appears inside another node |
| `precedes` / `follows` | positional ordering |

## Pitfalls (all observed in this repo)

1. **`not` accepts a single sub-rule only** — `not: any: [...]` parses but is
   **silently ignored**. Wrap the alternatives with `regex` inside `not.any` is
   fine — the bug is `pattern` alternatives under `not`. Prefer:
   ```yaml
   not:
     any:
       - regex: "^async def \\w+\\("
       - regex: "^def __init__\\("
   ```
2. **`$$$ARGS` needs a trailing comma** — `async def $NAME(self, $ID: UUID, $$$ARGS)`
   does not match `async def get(self, item_id: UUID) -> Item | None:` (single
   param). The trailing `$$$ARGS` requires a comma after the last literal
   param. When you need "first param is UUID regardless of arity", use regex:
   ```yaml
   regex: "^async def (get|update|delete)\\(\\s*self,\\s*\\w+: UUID"
   ```
   The `\\s*` are not decoration: a formatter wraps a long signature, and a
   regex written against one line then fails a **typing** rule for a
   **formatting** reason. Measured here — it decided a table's name before the
   rule was fixed. A rule matches the construct, never its line width.
3. **Rust regex has no lookahead** — `(?!__init__)` fails to parse. Use
   `not: any: [regex A, regex B]` instead.
4. **`constraints` lives next to `rule:`** — putting it inside `rule:` throws
   "unknown field `constraints`".
5. **`pattern` with return type** — `-> $_` must be included in the pattern when
   matching functions that declare return types; a bare signature pattern won't
   match them.
6. **`kind` inside `pattern` object is ignored** — set `kind` at the rule level,
   not inside a pattern object.
7. **YAML quoting** — `$ID: UUID` inside a double-quoted string is fine, but
   unquoted `pattern: async def $NAME($$$ARGS)` with `:` in params breaks YAML.
   Quote patterns containing `:` or `#`.

## Adding a New Rule

1. Create `.omp/ast-grep/rules/<scope>/<name>.yml` following the format above
2. Validate against real code + a deliberate violation:
   ```bash
   frontend/node_modules/.bin/ast-grep scan --rule .omp/ast-grep/rules/<scope>/<name>.yml <path> --json --include-metadata
   ```
   - Negative rule: must match the violation, must NOT match valid code
   - Positive rule: must match valid code
3. Ensure the owning hook already calls `runAstRules` with that scope dir; if
   the scope is new, wire it in the hook and add the row to `omp-hooks.md`
   "AST Rule Contract" table
4. Run `make verify`


## Rationale Comment

A structural rule reads as an assertion with no argument: the pattern says what
is rejected and never why. Every rule therefore carries a `#` comment **above
`rule:`** giving the reason - the failure it prevents, or the drift it catches.
Without it the next reader cannot tell a real invariant from someone's taste, and
deleting the rule looks free.

Where a pattern is subtle (a metavariable constraint, `stopBy: end`, an
alternation that a regex could not express), the comment says why that shape was
needed. `check-ast-rules` fails a rule with no comment above `rule:`.

## Test File Naming

A test file is named `<scope>-<rule>-test.yml` after the rule it proves -
`ast-grep/rules/router/write-auth.yml` -> `ast-grep/tests/router-write-auth-test.yml`.
The runner finds tests by `id:`, so a mismatched name still passes the runner;
it fails `check-ast-rules`, because a human looking for one rule's proof should
not have to grep for it.

## Never Do These

- Put rule logic in hook code — rules live in `.omp/ast-grep/rules/*.yml`, hooks only call `runAstRules`
- Use `not: any: [...]` with `pattern` alternatives — silently ignored (pitfall 1)
- Use lookahead/backreferences in `regex` — Rust regex rejects them
- Forget `expect: present` on positive rules — a missing rule match would
  silently pass
- Reference a rule dir from more than one hook — `check-omp-hooks` flags it
- Skip validating a new rule against both valid code and a deliberate violation
- Repeat the scope in the filename (`batch/batch-job-async.yml`) — the
  directory is the scope
- Abbreviate the scope in the filename (`env-` for `environment/`)
- Use underscores or mixed case in filenames — lowercase, hyphen-separated only
- Rename a rule without updating `omp-hooks.md` and the domain rule's
  Validation table — `check-omp-hooks` flags the stale reference
- Add a rule without a doc row — `check-omp-hooks` flags the orphan
- Re-implement a rule's declared `owns:` token in a TS hook regex — one owner only
- Ship a rule without a case file in `.omp/ast-grep/tests/` (`make check-ast-rules`)
- Let a missing ast-grep binary pass as "no issues" — the runner reports it
- Ship a rule with no `#` rationale comment above `rule:`
- Name a test file anything but `<scope>-<rule>-test.yml`
