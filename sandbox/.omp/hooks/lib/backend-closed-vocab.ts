// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join, relative } from "node:path";
import { resolveProjectRoot } from "./hook-project-root.ts";
import { queryDatabase } from "./hook-postgres.ts";

/**
 * Closed vocabularies — the `CHECK (col IN (...))` sets, against the live
 * database and against the schema `Literal` that publishes them.
 *
 * `alembic check` compares tables, columns, indexes and constraint *presence*;
 * autogenerate has never compared a CHECK constraint's body. Measured:
 * `SKIPPED` was added to `batch_run.status` in the model, the
 * schema `Literal` and the TypeScript union, no revision touched
 * `ck_batch_run_status`, and every gate passed. The first run that ended
 * SKIPPED was refused by the database, its ending was never written, and two
 * derive runs sat RUNNING for ever — a state the next fire then read as "a
 * derivation is already running" and stood down from.
 *
 * The reading here is the *live* one: model `CheckConstraint` against
 * `pg_constraint` in the running database. The other two sides of the same
 * vocabulary already have readers - `checkClosedVocabularyExposed`
 * (backend-domain-structure) compares the constraint with the schema
 * `Literal` that publishes it, and `checkMigrationPolicy` requires a changed
 * constraint to be carried by a revision that names it. What none of them had
 * was the database itself.
 *
 * Pure validation — no side effects. Called by the check-backend-domain
 * orchestrator.
 */

const projectRoot = resolveProjectRoot();

const modelsDir = join(projectRoot, "backend", "app", "models");

/**
 * Why the live comparison did not run, when it did not run. A gate that
 * compared nothing may not report a pass — the same rule `backend-orm-sync`
 * follows, and for the same measured reason.
 */
export let lastSkipReason: string | null = null;

/** One `col IN (...)` constraint as the model declares it. */
export interface ClosedVocabulary {
  /** `app/models/batch/run.py` — the file the constraint is written in. */
  readonly file: string;
  /** `batch_run` — the table it constrains. */
  readonly table: string;
  /** `ck_batch_run_status` — the name both the database and a revision use. */
  readonly name: string;
  /** `status` — the column whose values are closed. */
  readonly column: string;
  /** The values, as written. */
  readonly values: ReadonlySet<string>;
}

// ============================================================
// Functions
// ============================================================

/** Every `CheckConstraint("<col> IN (...)", name="ck_…")` under `app/models/`. */
export function listClosedVocabularies(): ClosedVocabulary[] {
  const found: ClosedVocabulary[] = [];
  for (const path of modelFiles(modelsDir)) {
    const file = `app/${relative(join(projectRoot, "backend", "app"), path)}`;
    found.push(...parseClosedVocabularies(readFileSync(path, "utf-8"), file));
  }
  return found;
}

/**
 * The vocabularies one model file declares.
 *
 * Exported because the same reading is made of a file that is not on disk:
 * `checkChangedVocabulariesAreMigrated` parses the upstream revision of the
 * model to see what this branch changed.
 */
export function parseClosedVocabularies(content: string, file: string): ClosedVocabulary[] {
  const table = /__tablename__\s*=\s*"([a-z0-9_]+)"/.exec(content)?.[1];
  if (table === undefined) return [];
  const found: ClosedVocabulary[] = [];
  // The body and the name are separated by a comma and any amount of
  // whitespace: the pair is written on one line when it fits and over four
  // when it does not, and both forms are the same declaration.
  for (const match of content.matchAll(/CheckConstraint\(\s*"([^"]+)"\s*,\s*name="(ck_[a-z0-9_]+)"/g)) {
    const parsed = /^\s*([a-z0-9_]+)\s+IN\s+\(([^)]*)\)\s*$/i.exec(match[1]);
    if (parsed === null) continue;
    found.push({
      file,
      table,
      name: match[2],
      column: parsed[1],
      values: quotedValues(parsed[2]),
    });
  }
  return found;
}

/**
 * The model's vocabularies against the database's own.
 *
 * Asked of `pg_constraint` rather than of a migration file, because the
 * question is what the database will accept tonight — a revision that exists
 * and was never applied answers nothing.
 */
export function checkVocabulariesMatchTheDatabase(): string[] {
  lastSkipReason = null;
  const declared = listClosedVocabularies();
  if (declared.length === 0) return [];

  let live: Map<string, Set<string>>;
  try {
    live = liveConstraints();
  } catch (error: unknown) {
    lastSkipReason = String(error instanceof Error ? error.message : error).slice(0, 120);
    return [];
  }

  const issues: string[] = [];
  for (const vocabulary of declared) {
    const actual = live.get(vocabulary.name);
    if (actual === undefined) {
      issues.push(
        `${vocabulary.file}: ${vocabulary.name} is declared on the model but the database has no ` +
          "such constraint — the revision that creates it is missing or unapplied",
      );
      continue;
    }
    const difference = describeDifference(vocabulary.values, actual);
    if (difference !== null) {
      issues.push(
        `${vocabulary.name}: the model and the database close ${vocabulary.table}.` +
          `${vocabulary.column} over different values (${difference}) — alembic autogenerate ` +
          "does not compare a CHECK body, so this needs its own revision " +
          "(drop_constraint + create_check_constraint)",
      );
    }
  }
  return issues;
}

/** Every `ck_*` constraint the running database holds, as value sets. */
function liveConstraints(): Map<string, Set<string>> {
  const rows = queryDatabase(
    "SELECT conname || '|' || pg_get_constraintdef(oid) FROM pg_constraint " +
      "WHERE conname LIKE 'ck\\_%' AND contype = 'c'",
  );
  const live = new Map<string, Set<string>>();
  for (const row of rows) {
    const split = row.indexOf("|");
    if (split === -1) continue;
    const name = row.slice(0, split);
    const definition = row.slice(split + 1);
    // Postgres prints a membership test as `= ANY (ARRAY['A'::…, 'B'::…])`,
    // whatever the CHECK was written as. A definition with no ARRAY is a
    // different kind of check (a range, a nullability pair) and has no
    // vocabulary to compare.
    if (!/=\s*ANY\s*\(/.test(definition)) continue;
    live.set(name, quotedValues(definition));
  }
  return live;
}

/** The quoted strings of a SQL list or a `Literal[...]`, as a set. */
function quotedValues(source: string): Set<string> {
  const values = new Set<string>();
  for (const match of source.matchAll(/'([^']*)'|"([^"]*)"/g)) {
    values.add(match[1] ?? match[2]);
  }
  return values;
}

/** What each side has that the other does not, or null when they agree. */
function describeDifference(left: ReadonlySet<string>, right: ReadonlySet<string>): string | null {
  const onlyLeft = [...left].filter((value) => !right.has(value)).sort();
  const onlyRight = [...right].filter((value) => !left.has(value)).sort();
  if (onlyLeft.length === 0 && onlyRight.length === 0) return null;
  const parts: string[] = [];
  if (onlyLeft.length > 0) parts.push(`declared only: ${onlyLeft.join(", ")}`);
  if (onlyRight.length > 0) parts.push(`other side only: ${onlyRight.join(", ")}`);
  return parts.join("; ");
}

/** Every Python module under a directory, recursively. */
function modelFiles(directory: string): string[] {
  if (!existsSync(directory)) return [];
  const files: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...modelFiles(path));
    else if (entry.name.endsWith(".py")) files.push(path);
  }
  return files;
}
