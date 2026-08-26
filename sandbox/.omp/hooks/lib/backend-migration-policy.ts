/**
 * Migration policy shared by the migration pre-hook and post-hook.
 *
 * Owns the three questions both hooks must answer identically:
 *   - is a revision already on the Git upstream (and therefore immutable)?
 *   - which tables does a revision touch (the one-table-per-revision rule)?
 *   - which integration migrations and seeded operation codes exist on disk
 *     (discovery is filesystem-driven — hardcoded revision lists are forbidden)?
 *
 * Keeping this in one module is what stops the pre-hook and post-hook from
 * disagreeing about whether an edit is allowed.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

/** Migrations live in one place; the git queries below are scoped to it. */
const MIGRATIONS_PATH = "backend/alembic/versions";

/** Upstream file sets per upstream commit — invalidated by a push, not by time. */
const upstreamCache = new Map<string, { pushed: Set<string>; modified: Set<string> }>();
const versionsDir = join(projectRoot, "backend", "alembic", "versions");

// Revisions 1–6 predate the enforced one-table/immutability policy. They are
// historical baseline and must not make every new check fail because of a
// pre-policy local correction. Every revision from 7 onward is enforced.
const FIRST_ENFORCED_MIGRATION_REVISION = 7;

export function isGrandfatheredMigration(filenameOrPath: string): boolean {
  const filename = filenameOrPath.split("/").pop() ?? "";
  const revision = Number(filename.split("_", 1)[0]);
  return Number.isInteger(revision) && revision < FIRST_ENFORCED_MIGRATION_REVISION;
}

export function isPushedMigration(relativePath: string): boolean {
  if (isGrandfatheredMigration(relativePath)) return false;
  const upstream = getUpstream();
  return upstream !== null && upstreamState(upstream).pushed.has(relativePath);
}

export function listIntegrationMigrationFiles(): string[] {
  if (!existsSync(versionsDir)) return [];
  return readdirSync(versionsDir)
    .filter((filename: string) => filename.endsWith(".py") && filename.includes("_integration_"))
    .sort();
}

/** The table whose rows are integration operations — the discovery filter. */
const OPERATION_TABLE = "integration_operation";

/** The live table that makes an operation executable: without a row here it 422s. */
const FIELD_TABLE = "integration_field";

/** The parent whose replacement cascades operations away. */
const PROVIDER_TABLE = "integration_provider";

/** A provider `_replace_` deletes its row first; operations cascade with it. */
const PROVIDER_DELETE = /\.delete\(\)|DELETE\s+FROM\s+integration_provider/i;

/**
 * The canonical paging inputs an operation may declare, by family.
 *
 * Paging is a property of the endpoint, not of the client: some providers page,
 * some return everything. The canonical `key` is ours and standardised; the
 * `wire_path` stays whatever the provider calls it (`pageNo`/`numOfRows`,
 * `startIdx`/`endIdx`).
 *
 * A family is added by the first live operation that needs it — together with its
 * wire mapping and its `.http` proof — and never before: this file once carried a
 * `range_start`/`range_end` pair for exactly one operation that a provider replace
 * had already deleted, so the standard had no caller and no way to be wrong out loud.
 * RANGE is back because I1250 (식품(첨가물)품목제조보고) pages by row index and has no
 * page number at all.
 *
 * Declaring half a family — or two families at once — is the failure this exists to
 * name: a window is a position and a size, from the same family.
 */
export const PAGING_FAMILIES: Readonly<Record<string, readonly string[]>> = {
  PAGE: ["page_no", "num_of_rows"],
  RANGE: ["range_start", "range_end"],
};

export const PAGING_KEYS: readonly string[] = Object.values(PAGING_FAMILIES).flat();

/** A `"code": "…"` literal in a seeded row. */
const CODE_LITERAL = /"code":\s*"([a-z0-9-]+)"/g;

/** `OPERATION_ID = uuid5(NAMESPACE_URL, "<seed>")` — the join key between seeds. */
const OPERATION_SEED = /OPERATION_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"/;

/** `PROVIDER_ID = uuid5(NAMESPACE_URL, "<seed>")` — which provider a file configures. */
const PROVIDER_SEED = /PROVIDER_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"/;

/**
 * `op.bulk_insert(` — the call site itself. The arguments are read by balancing
 * brackets, not by a regex.
 *
 * Measured: a regex requiring the row list to end on its own line matched only
 * multi-line literals, so revisions 51, 58 and 61 — every operation seed written
 * since — were invisible, and discovery answered with revision 21's row. A reader
 * that silently reads a three-revision-old seed is worse than one that refuses to
 * read at all.
 */
const BULK_INSERT_CALL = /op\.bulk_insert\(/g;

/**
 * `"response_root": "/body/items"` or `"response_root": PAGE_ROOT` in a seeded row.
 *
 * Seeds name the pointer through a module constant, so the identifier form is read
 * too — a check that only saw string literals would call every constant-using seed
 * rootless, which is the shape a paging operation is forbidden to have.
 */
const RESPONSE_ROOT = /"response_root":\s*(?:"([^"]*)"|([A-Z_][A-Z0-9_]*))/;

/** `"path_template": "/api/{key}/…"` or `"path_template": PATH_TEMPLATE` in a seeded row. */
const PATH_TEMPLATE = /"path_template":\s*(?:"([^"]*)"|([A-Z_][A-Z0-9_]*))/;

/** One `op.bulk_insert` call: the table argument and the rows argument, verbatim. */
interface BulkInsert {
  table: string;
  rows: string;
}

/**
 * Every `op.bulk_insert` call a migration performs **on the way up**.
 *
 * Nested brackets are why the arguments are split by balance and not by a regex: a
 * seeded `request_schema` carries JSON with its own `[` and `]`, and a lazy pattern
 * stops at the first of them.
 *
 * Calls written inside `def downgrade()` are skipped. Measured: revision 61 restores
 * the previous revision's row on the way down, and reading that insert too made
 * discovery report the *old* `response_root` — `/body/items/0`, the index pin the
 * upgrade exists to remove. A reverse path is not a claim about the database's state.
 */
function bulkInserts(content: string): BulkInsert[] {
  const downgradeAt = content.search(/\ndef downgrade\(\)/);
  const calls: BulkInsert[] = [];
  for (const call of content.matchAll(BULK_INSERT_CALL)) {
    const callAt = call.index ?? 0;
    if (downgradeAt >= 0 && callAt > downgradeAt) continue;
    let depth = 1;
    let split = -1;
    let index = callAt + call[0].length;
    const start = index;
    for (; index < content.length && depth > 0; index += 1) {
      const character = content[index];
      if ("([{".includes(character)) depth += 1;
      else if (")]}".includes(character)) depth -= 1;
      else if (character === "," && depth === 1 && split < 0) split = index;
    }
    if (depth !== 0 || split < 0) continue;
    calls.push({
      table: content.slice(start, split).trim(),
      rows: content.slice(split + 1, index - 1).trim(),
    });
  }
  return calls;
}

/**
 * Columns a seed migration binds that the model does not have.
 *
 * A `table()` binding is a promise about the schema, and nothing static checked
 * it: measured, a local model wrote `display_name`, `description` and
 * `url_template` onto `integration_operation` - none of them exist - and the
 * mistake only surfaced as `sqlite3.OperationalError` inside a test. The model
 * file is the source of truth here, so the check reads both.
 */
export function listUnknownSeedColumns(): string[] {
  const modelPath = join(projectRoot, "backend", "app", "models", "integration.py");
  if (!existsSync(versionsDir) || !existsSync(modelPath)) return [];
  const model = readFileSync(modelPath, "utf-8");
  const known = new Map<string, Set<string>>();
  // `class IntegrationOperation(Base, AuditMixin):` … `__tablename__ = "integration_operation"`
  for (const block of model.split(/\nclass /).slice(1)) {
    const table = /__tablename__\s*=\s*"([a-z_]+)"/.exec(block)?.[1];
    if (table === undefined) continue;
    const columns = new Set<string>(["created_by", "updated_by", "created_at", "updated_at"]);
    for (const match of block.matchAll(/^\s{4}([a-z_][a-z0-9_]*)\s*:\s*Mapped\[/gm)) columns.add(match[1]);
    known.set(table, columns);
  }
  const issues: string[] = [];
  // Only the seeds a replay still runs. A migration written at revision 13 bound
  // `response_schema`, a column that existed then and was dropped later - judging
  // history against today's model reports four failures nobody can fix.
  // A provider replace cascades its operations away, so a seed older than its
  // owner's newest replace never runs again. Measured: revision 16 seeds an
  // operation revision 20 removed, and binds `response_schema` - a column that
  // existed then. The rule is the revision, not discoverability: a seed this
  // module cannot parse still runs at migration time, and its columns still have
  // to exist.
  // Suppression needs proof, and there are two kinds of file here. A seed whose
  // operation this module can read but whose row a later provider replace
  // cascaded away never runs again - revision 16 binds `response_schema`, a
  // column that existed then, and there is nothing to fix. A seed the module
  // *cannot* read is the opposite: it still runs, so its columns still have to
  // exist, and suppressing it is how a wrong column reaches the database.
  const live = new Set(listIntegrationOperations().map((operation) => operation.code));
  const unreadable = new Set(listUnreadableOperationSeeds().map((line) => line.split(":")[0]));
  for (const filename of liveSeedFiles()) {
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    const named = [...content.matchAll(/"code":\s*"([a-z0-9-]+)"/g)].map((match) => match[1]);
    const dead = !unreadable.has(filename) && named.length > 0 && named.every((code) => !live.has(code));
    if (dead) continue;
    for (const binding of content.matchAll(/table\(\s*"([a-z_]+)"([\s\S]*?)\n\s*\)/g)) {
      const columns = known.get(binding[1]);
      if (columns === undefined) continue;
      for (const column of binding[2].matchAll(/column\(\s*"([a-z_]+)"/g)) {
        if (columns.has(column[1])) continue;
        issues.push(
          `${filename}: binds ${binding[1]}.${column[1]}, which the model does not declare - ` +
            `copy the column list from the model (${[...columns].sort().join(", ")})`,
        );
      }
    }
  }
  return issues;
}

/**
 * Pushed migrations a shell command would move, delete or rewrite.
 *
 * The write/edit guard only sees tool paths. Measured: a local model asked to
 * follow the new seed-naming rule renamed two **published** revisions with
 * `mv` - the one operation the rule exempts - and nothing stopped it, because a
 * rename is not a write. A published revision is immutable however the bytes
 * move, so the same policy has to read commands too.
 *
 * Read-only commands are not touched: naming a migration in `cat`, `grep` or
 * `git log` is how anyone learns what it did.
 */
export function listPushedMigrationsMutatedBy(command: string): string[] {
  // Verbs that relocate, delete or rewrite a file. `git mv`/`git rm` are the
  // same acts through another door, and a `>` redirect rewrites in place.
  const MUTATES = /\b(mv|rm|cp|rename|install|truncate|shred|sed\s+-i|tee|dd)\b|>\s*\S*backend\/alembic|git\s+(mv|rm)\b/;
  if (!MUTATES.test(command)) return [];
  const named = new Set<string>();
  for (const match of command.matchAll(/[\w./-]*alembic\/versions\/([\w.-]+\.py)/g)) named.add(match[1]);
  for (const match of command.matchAll(/(?:^|[\s"'(/])(\d+_[\w-]+\.py)\b/g)) named.add(match[1]);
  const pushed: string[] = [];
  for (const filename of named) {
    if (isPushedMigration(join("backend", "alembic", "versions", filename))) pushed.push(filename);
  }
  return pushed.sort();
}

/**
 * Seed files whose name does not say what they seed.
 *
 * `<rev>_(seed|replace)_<subject>_integration_<table>.py`, and the subject is the
 * row's own identity: the operation slug for `operation`/`field` seeds, the
 * provider slug for `provider`/`secret` seeds. Measured on this repository:
 * revisions 66, 70 and 72 seed three different operations under one name, so
 * neither a reader nor a filename-keyed tool can tell them apart - and the tool
 * silently kept only the newest.
 *
 * Published files are named here rather than renamed: a pushed migration is
 * immutable by policy, and the identity-keyed reader no longer depends on the
 * name being right.
 */
export function listMisnamedSeedFiles(): string[] {
  if (!existsSync(versionsDir)) return [];
  const issues: string[] = [];
  for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
    const parsed = /^\d+_(seed|replace)_(.+)_integration_([a-z_]+)\.py$/.exec(filename);
    if (parsed === null) continue;
    const [, kind, subject, table] = parsed;
    // A pushed migration is immutable by policy, so the rule can only bind files
    // that are still being written. The identity-keyed reader no longer depends
    // on the name being right, which is what makes grandfathering safe.
    if (isPushedMigration(join("backend", "alembic", "versions", filename))) continue;
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    const operationSeed = OPERATION_SEED.exec(content)?.[1];
    const providerSeed = PROVIDER_SEED.exec(content)?.[1];
    const owns = table === "operation" || table === "field";
    const identity = owns ? operationSeed : providerSeed;
    if (identity === undefined) continue;
    const parts = identity.split("/");
    // `…/<provider>/<operation>` for an operation, `…/<provider>/provider` for the
    // provider itself: the row's own name is the last segment except there.
    const slug = owns ? (parts[parts.length - 1] ?? "") : (parts[parts.length - 2] ?? "");
    const wanted = slug.replace(/-/g, "_");
    const accepted = new Set([wanted, wanted.replace(/^search_/, ""), wanted.replace(/^mfds_/, "")]);
    if (accepted.has(subject)) continue;
    issues.push(
      `${filename}: names '${subject}', but it seeds '${slug}' - rename it to ` +
        `<revision>_${kind}_${[...accepted].sort((a, b) => a.length - b.length)[0]}_integration_${table}.py, ` +
        "because one file per identity is what makes a listing readable and a superseding revision unambiguous",
    );
  }
  return issues;
}

/**
 * The newest seed per **identity**, not per filename.
 *
 * Grouping by the filename's subject looked equivalent and was not: three
 * different operations of one provider are all called
 * `<rev>_seed_food_safety_korea_integration_operation.py`, so a filename-keyed
 * reader treats revision 72 as superseding 70 and 66 - and silently stops
 * checking them. Identity is what the seed writes: the operation seed string for
 * operation/field rows, the provider seed string otherwise. Supersession is real
 * only between files that seed the *same* row.
 */
function liveSeedFiles(): string[] {
  const newest = new Map<string, { revision: number; filename: string }>();
  for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py"))) {
    const parsed = /^(\d+)_(?:seed|replace)_(.+)_integration_([a-z_]+)\.py$/.exec(filename);
    if (parsed === null) continue;
    const revision = Number.parseInt(parsed[1], 10);
    if (Number.isNaN(revision)) continue;
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    const identity =
      OPERATION_SEED.exec(content)?.[1] ?? PROVIDER_SEED.exec(content)?.[1] ?? parsed[2];
    const key = identity + "/" + parsed[3];
    const previous = newest.get(key);
    if (previous === undefined || previous.revision < revision) newest.set(key, { revision, filename });
  }
  return [...newest.values()].sort((left, right) => left.revision - right.revision).map((entry) => entry.filename);
}

/** Raw SQL that writes the operation table — unreadable by design, so rejected. */
const RAW_OPERATION_INSERT = new RegExp(`INSERT\\s+INTO\\s+${OPERATION_TABLE}\\b`, "i");

export interface IntegrationOperation {
  code: string;
  /** The uuid5 seed string its id derives from, or null when the file omits it. */
  seed: string | null;
  /** A live `integration_field` seed shares this operation's seed string. */
  configured: boolean;
  /** The `response_root` its newest seed writes, or null when it maps one record. */
  root: string | null;
  /** The `path_template` its newest seed writes, or null when the file omits it. */
  pathTemplate: string | null;
}

/**
 * Table bindings a migration makes: `x = table("t")`, helpers that return one, and
 * `x = helper()`.
 *
 * `helpers` is returned because the table argument of an insert is written both ways —
 * `operation = _operation_table()` then `bulk_insert(operation, …)`, and
 * `bulk_insert(_operation_table(), …)` directly. Measured: knowing only the first
 * spelling made a seeded operation invisible, so nothing demanded its request file or
 * its contract test.
 */
function tableBindings(content: string): {
  bound: Map<string, string>;
  helpers: Map<string, string>;
  tables: Set<string>;
} {
  const bound = new Map<string, string>();
  const helpers = new Map<string, string>();
  // The body may not cross into the next function: an unbounded gap read the `table(`
  // of the *following* helper, so `_id` was recorded as the operation table and the
  // real helper was never bound. Measured — a seeded operation then had no resolvable
  // insert target at all.
  const helperReturn = /def\s+(\w+)\s*\([^)]*\)[^:]*:((?:(?!\ndef )[\s\S]){0,400}?)return\s+table\(\s*"([^"]+)"/g;
  for (const match of content.matchAll(helperReturn)) {
    helpers.set(match[1], match[3]);
  }
  for (const match of content.matchAll(/(\w+)\s*=\s*table\(\s*"([^"]+)"/g)) bound.set(match[1], match[2]);
  for (const match of content.matchAll(/(\w+)\s*=\s*(\w+)\(\)/g)) {
    const table = helpers.get(match[2]);
    if (table !== undefined) bound.set(match[1], table);
  }
  return { bound, helpers, tables: new Set([...bound.values(), ...helpers.values()]) };
}

/** The table an insert writes: an inline `table("t")`, a bound variable, or `helper()`. */
function insertTarget(insert: BulkInsert, bindings: ReturnType<typeof tableBindings>): string | undefined {
  if (insert.table.startsWith("table(")) return /table\(\s*"([^"]+)"/.exec(insert.table)?.[1];
  const call = /^(\w+)\(\s*\)$/.exec(insert.table);
  if (call !== null) return bindings.helpers.get(call[1]);
  return bindings.bound.get(insert.table);
}

/**
 * The `upgrade()` body of a migration — the only path a database actually took.
 *
 * A `downgrade` that deletes a row says nothing about what the migration did on the
 * way up. Measured: reading the whole file made the second provider's seed look like a
 * replace, which cascaded the first provider's operations out of discovery and left
 * the runner reporting a live operation as "no migration seeds it".
 */
function upgradeBody(content: string): string {
  const match = /\ndef upgrade\(\)[^:]*:\n([\s\S]*?)(?=\ndef |$)/.exec(content);
  return match?.[1] ?? "";
}

/**
 * The body of every function the rows blob calls, and of the functions those call.
 *
 * One level was enough while every seed inlined its row dict. A `_previous_row()`
 * that returns `_row() | {…}` hides the `"code"` literal one call further down, and
 * a reader that stopped at the first level called that seed unreadable.
 */
function calledHelperBodies(content: string, rows: string, depth = 2): string {
  let text = "";
  for (const call of rows.matchAll(/(\w+)\s*\(/g)) {
    const body = new RegExp(`def\\s+${call[1]}\\s*\\([^)]*\\)[^:]*:([\\s\\S]*?)\\n(?=\\S|def )`).exec(content);
    if (body === null) continue;
    text += body[1];
    if (depth > 1) text += calledHelperBodies(content, body[1], depth - 1);
  }
  return text;
}

/**
 * Every operation the migrations put into `integration_operation`, with whether
 * a live `integration_field` seed makes it executable.
 *
 * Discovery is by **target table**, not by filename. The filename rule that
 * preceded it read only `_integration_operation` files and, once any `_replace_`
 * existed, dropped every `_seed_` one — measured consequence:
 * `search-domestic-food-products` (revision 16) was invisible, so the gates that
 * demand a request file and a contract-test anchor per integration both passed
 * while a live external API had neither.
 *
 * `configured` joins operation and field seeds through the `uuid5` seed string
 * they share, because the id itself is derived and cannot be compared as a
 * literal. An operation without a live field seed cannot resolve its path
 * template and answers 422 — that is a state to declare, not to declare in
 * production.
 *
 * A provider `_replace_` deletes its row and re-inserts it, and
 * `integration_operation.provider_id` is ON DELETE CASCADE — so every operation
 * seeded **before** that revision is gone unless a later revision seeds it
 * again. Measured: `search-domestic-food-products` (revision 16) was erased by
 * the provider replace at revision 20 and answers exactly like an operation that
 * never existed. Reporting it would demand a request file, a contract-test
 * anchor and a paging contract for a row no database has.
 */
export function listIntegrationOperations(): IntegrationOperation[] {
  if (!existsSync(versionsDir)) return [];
  const seedOf = new Map<string, string | null>();
  const seededAt = new Map<string, number>();
  const configuredSeeds = new Set<string>();
  const rootOf = new Map<string, string | null>();
  const templateOf = new Map<string, string | null>();
  const providerOf = new Map<string, string>();
  const providerReplacedAt = new Map<string, number>();
  for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
    const revision = Number.parseInt(filename.split("_")[0], 10);
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    const bindings = tableBindings(content);
    const { tables } = bindings;
    const seed = OPERATION_SEED.exec(content)?.[1] ?? null;
    const providerSeed = PROVIDER_SEED.exec(content)?.[1] ?? null;
    if (tables.has(FIELD_TABLE) && seed !== null) configuredSeeds.add(seed);
    if (tables.has(PROVIDER_TABLE) && providerSeed !== null && PROVIDER_DELETE.test(upgradeBody(content))) {
      providerReplacedAt.set(providerSeed, Math.max(providerReplacedAt.get(providerSeed) ?? 0, revision));
    }
    if (!tables.has(OPERATION_TABLE)) continue;
    for (const insert of bulkInserts(content)) {
      if (insertTarget(insert, bindings) !== OPERATION_TABLE) continue;
      const scope = `${insert.rows}${calledHelperBodies(content, insert.rows)}`;
      const root = seededRoot(content, scope);
      const template = seededPathTemplate(content, scope);
      for (const code of scope.matchAll(CODE_LITERAL)) {
        seedOf.set(code[1], seed);
        seededAt.set(code[1], revision);
        rootOf.set(code[1], root);
        templateOf.set(code[1], template);
        if (providerSeed !== null) providerOf.set(code[1], providerSeed);
      }
    }
  }
  for (const [code, revision] of seededAt) {
    const replaced = providerReplacedAt.get(providerOf.get(code) ?? "") ?? 0;
    if (revision < replaced) seedOf.delete(code);
  }
  return [...seedOf.entries()]
    .map(([code, seed]) => ({
      code,
      seed,
      configured: seed !== null && configuredSeeds.has(seed),
      root: rootOf.get(code) ?? null,
      pathTemplate: templateOf.get(code) ?? null,
    }))
    .sort((left, right) => left.code.localeCompare(right.code));
}

export function listIntegrationOperationCodes(): string[] {
  return listIntegrationOperations().map((operation) => operation.code);
}

/** The `response_root` a seeded row writes, following one constant indirection. */
function seededRoot(content: string, scope: string): string | null {
  return seededLiteral(content, scope, RESPONSE_ROOT);
}

/** The `path_template` a seeded row writes, following one constant indirection. */
function seededPathTemplate(content: string, scope: string): string | null {
  return seededLiteral(content, scope, PATH_TEMPLATE);
}

function seededLiteral(content: string, scope: string, pattern: RegExp): string | null {
  const match = pattern.exec(scope);
  if (match === null) return null;
  if (match[1] !== undefined) return match[1];
  const literal = new RegExp(`^${match[2]}\\s*=\\s*"([^"]*)"`, "m").exec(content);
  return literal?.[1] ?? null;
}

/**
 * Caller-supplied REQUEST field keys per operation code.
 *
 * A seeded input nobody ever sends is an untested parameter: the request file
 * used to exercise one of `search-food-nutrition`'s seven CALLER fields, so six
 * wire mappings (`RESEARCH_YMD`, `MAKER_NM`, …) had never been called once.
 *
 * Both shapes the field seeds use are read: a positional tuple list — with or without
 * a location column between the wire name and the source
 * (`('food_name', 'FOOD_NM_KR', 'CALLER', …)`, `('range_start', 'range_start', 'PATH',
 * 'CALLER', …)`) — and explicit dicts with `"key"` and `"value_source"`. SECRET and
 * LITERAL fields are excluded: the caller does not supply them. Measured: a reader
 * that assumed the source was always the third element saw none of I1250's inputs, so
 * its paging keys read as "the operation seeds none".
 *
 * Only the **newest** revision that seeds the field table counts. A `_replace_`
 * deletes the operation's rows before inserting its own, so unioning every
 * revision resurrects keys that no longer exist: renaming `maker_nm` to
 * `maker_name` demanded a 200 block for both, one of which the API would reject.
 */
export function listIntegrationCallerInputs(): Map<string, string[]> {
  const bySeed = new Map<string, { revision: number; keys: string[] }>();
  if (existsSync(versionsDir)) {
    for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
      const content = readFileSync(join(versionsDir, filename), "utf-8");
      const { tables } = tableBindings(content);
      const seed = OPERATION_SEED.exec(content)?.[1] ?? null;
      if (!tables.has(FIELD_TABLE) || seed === null) continue;
      const revision = Number.parseInt(filename.split("_")[0], 10);
      if (Number.isNaN(revision)) continue;
      const previous = bySeed.get(seed);
      if (previous !== undefined && previous.revision > revision) continue;
      const keys = new Set<string>();
      const callerTuple = /\(\s*'([a-z0-9_]+)'\s*,\s*'[^']*'\s*(?:,\s*'[A-Z_]+'\s*)?,\s*'CALLER'/g;
      for (const tuple of content.matchAll(callerTuple)) {
        keys.add(tuple[1]);
      }
      for (const entry of content.matchAll(/"key":\s*"([a-z0-9_]+)"[\s\S]{0,240}?"value_source":\s*"CALLER"/g)) {
        keys.add(entry[1]);
      }
      bySeed.set(seed, { revision, keys: [...keys] });
    }
  }
  const byCode = new Map<string, string[]>();
  for (const operation of listIntegrationOperations()) {
    if (operation.seed === null) continue;
    const seeded = bySeed.get(operation.seed);
    if (seeded !== undefined) byCode.set(operation.code, [...seeded.keys].sort());
  }
  return byCode;
}

/**
 * PATH-located REQUEST wire names per operation code, from the newest field seed.
 *
 * A `path_template` placeholder with no field to fill it is unresolvable at call time
 * (`Request path variables are unresolved`), and nothing static caught it: measured on a
 * seed whose template ended in `/{filters}` while the filters were PATH_QUERY rows that
 * append their own segment.
 */
export function listIntegrationPathFields(): Map<string, string[]> {
  const bySeed = new Map<string, { revision: number; wires: string[] }>();
  if (existsSync(versionsDir)) {
    for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
      const content = readFileSync(join(versionsDir, filename), "utf-8");
      const { tables } = tableBindings(content);
      const seed = OPERATION_SEED.exec(content)?.[1] ?? null;
      if (!tables.has(FIELD_TABLE) || seed === null) continue;
      const revision = Number.parseInt(filename.split("_")[0], 10);
      if (Number.isNaN(revision)) continue;
      const previous = bySeed.get(seed);
      if (previous !== undefined && previous.revision > revision) continue;
      const wires = new Set<string>();
      for (const tuple of content.matchAll(/\(\s*'[a-z0-9_]+'\s*,\s*'([^']+)'\s*,\s*'PATH'/g)) {
        wires.add(tuple[1]);
      }
      for (const entry of content.matchAll(/"wire_path":\s*"([^"]+)"[\s\S]{0,240}?"location":\s*"PATH"/g)) {
        wires.add(entry[1]);
      }
      for (const entry of content.matchAll(/"location":\s*"PATH"[\s\S]{0,240}?"wire_path":\s*"([^"]+)"/g)) {
        wires.add(entry[1]);
      }
      bySeed.set(seed, { revision, wires: [...wires] });
    }
  }
  const byCode = new Map<string, string[]>();
  for (const operation of listIntegrationOperations()) {
    if (operation.seed === null) continue;
    const seeded = bySeed.get(operation.seed);
    if (seeded !== undefined) byCode.set(operation.code, [...seeded.wires].sort());
  }
  return byCode;
}

/**
 * CALLER filter keys that are nothing but the provider's wire name, lower-cased.
 *
 * `skill://integration` takes the key from the column's documented description, not
 * from the wire name: the key is the caller-facing contract, and a key that is just
 * the provider's spelling lower-cased publishes that spelling to every caller, so
 * swapping provider breaks them. A benchmarked run keyed all four of an operation's
 * filters that way and passed every hook and all 150 tests (measured) — the
 * convention was stated in three places and enforced in none.
 *
 * Only filters are judged. A provider wire name is upper-case here, and the pattern
 * requires that, so path parameters never match: their `wire_path` is already the
 * caller's word (`service_key`, `range_start`) and lower-case. Verified against every
 * field seed in the tree: no false positive.
 *
 * Newest seed per owner, like every other reader in this module — a `_replace_`
 * supersedes the keys it replaced.
 */
export function listWireNamedCallerKeys(): string[] {
  const bySeed = new Map<string, { revision: number; filename: string; bad: string[] }>();
  if (!existsSync(versionsDir)) return [];
  for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    const { tables } = tableBindings(content);
    const seed = OPERATION_SEED.exec(content)?.[1] ?? null;
    if (!tables.has(FIELD_TABLE) || seed === null) continue;
    const revision = Number.parseInt(filename.split("_")[0], 10);
    if (Number.isNaN(revision)) continue;
    const previous = bySeed.get(seed);
    if (previous !== undefined && previous.revision > revision) continue;
    const bad: string[] = [];
    const tuple = /\(\s*'([a-z0-9_]+)'\s*,\s*'([A-Z0-9_]+)'\s*,\s*'(?:PATH_QUERY|QUERY)'\s*,\s*'CALLER'/g;
    for (const match of content.matchAll(tuple)) {
      if (match[1] === match[2].toLowerCase()) bad.push(`${match[1]} (wire ${match[2]})`);
    }
    const dict =
      /"key":\s*"([a-z0-9_]+)"[\s\S]{0,240}?"wire_path":\s*"([A-Z0-9_]+)"[\s\S]{0,240}?"location":\s*"(?:PATH_QUERY|QUERY)"/g;
    for (const match of content.matchAll(dict)) {
      if (match[1] === match[2].toLowerCase()) bad.push(`${match[1]} (wire ${match[2]})`);
    }
    bySeed.set(seed, { revision, filename, bad });
  }
  const issues: string[] = [];
  for (const { filename, bad } of bySeed.values()) {
    if (bad.length === 0) continue;
    issues.push(
      `alembic/versions/${filename}: CALLER filter key(s) are the wire name lower-cased — ` +
        `${bad.join(", ")}. The key is the caller-facing name and comes from the column's ` +
        "documented description; a wire-named key publishes the provider's spelling to every caller",
    );
  }
  return issues;
}

/**
 * Migrations that write the operation table in a shape this module cannot read.
 *
 * A silent miss is the failure mode being closed here: an unreadable seed used
 * to mean "no operation exists", so no request file and no contract test were
 * required. Three shapes are therefore reported instead of ignored: raw SQL, an
 * insert whose rows carry no `"code"` literal, and an insert whose rows are handed
 * over as a variable — measured, a refactor to `op.bulk_insert(operation, rows)`
 * made the newest operation seed invisible to every reader here while the database
 * kept serving it.
 */
export function listUnreadableOperationSeeds(): string[] {
  if (!existsSync(versionsDir)) return [];
  const unreadable: string[] = [];
  for (const filename of readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort()) {
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    if (RAW_OPERATION_INSERT.test(content)) {
      unreadable.push(`${filename}: writes ${OPERATION_TABLE} through raw SQL`);
      continue;
    }
    const bindings = tableBindings(content);
    if (!bindings.tables.has(OPERATION_TABLE)) continue;
    for (const insert of bulkInserts(content)) {
      const target = insertTarget(insert, bindings);
      if (target === undefined) {
        unreadable.push(
          `${filename}: bulk_insert names its table as \`${insert.table}\`, which this module ` +
            "cannot resolve — bind it to a variable or call the table helper directly",
        );
        continue;
      }
      if (target !== OPERATION_TABLE) continue;
      if (!insert.rows.startsWith("[")) {
        unreadable.push(
          `${filename}: bulk_insert into ${OPERATION_TABLE} passes rows as \`${insert.rows}\` — ` +
            "the rows must be a literal list so the seed can be read without running it",
        );
        continue;
      }
      const scope = `${insert.rows}${calledHelperBodies(content, insert.rows)}`;
      if (!new RegExp(CODE_LITERAL.source).test(scope)) {
        unreadable.push(`${filename}: bulk_insert into ${OPERATION_TABLE} carries no "code" literal`);
      }
    }
  }
  return unreadable;
}

const TABLE_PATTERNS = [
  /op\.(?:create_table|drop_table|add_column|drop_column|alter_column|batch_alter_table)\(\s*["']([^"']+)["']/g,
  /op\.create_index\(\s*[^,]+,\s*["']([^"']+)["']/g,
  /op\.drop_index\([^)]*table_name\s*=\s*["']([^"']+)["']/g,
  /op\.(?:create|drop)_(?:primary_key|unique_constraint|check_constraint|foreign_key|constraint)\(\s*[^,]+,\s*["']([^"']+)["']/g,
  /\b(?:ALTER|CREATE|DROP)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?["']?([a-zA-Z_][a-zA-Z0-9_]*)/gi,
  /\btable\(\s*["']([^"']+)["']/g,
];

/** The metadata block alembic generates, in the order it generates it. */
const METADATA_FIELDS = ["revision", "down_revision", "branch_labels", "depends_on"];

/**
 * Layout of one revision file. A migration is read years later, by someone
 * deciding whether it can be reverted — so the shape has to be uniform and the
 * reverse path has to state its own terms.
 */
function checkMigrationLayout(filename: string, content: string): string[] {
  const issues: string[] = [];

  // A revision's filename slug is its history entry. Measured (optimal-set
  // cell #1): `make migrate-gen m=""` produced `75_.py` — an empty slug the
  // gate accepted.
  if (!/^\d+_[a-z0-9][a-z0-9_]*\.py$/.test(filename)) {
    issues.push(
      `${filename}: filename needs a non-empty snake_case slug — \`NN_<what_it_does>.py\` ` +
        '(run `make migrate-gen m="<message>"` with a real message)',
    );
  }

  const docstring = /^"""([^\n]*)\n([\s\S]*?)"""/.exec(content);
  if (docstring === null) {
    issues.push(`${filename}: missing module docstring — the summary and Revision ID header`);
  } else {
    if (docstring[1].trim() === "") {
      issues.push(`${filename}: docstring summary line is empty — name the change`);
    }
    if (!/Revision ID:\s*\S/.test(docstring[2]) || !/Revises:/.test(docstring[2])) {
      issues.push(`${filename}: docstring must keep the "Revision ID:" / "Revises:" header`);
    }
  }

  const declared = /^revision:\s*str\s*=\s*["']([^"']+)["']/m.exec(content);
  const fromName = filename.split("_", 1)[0];
  if (declared === null) {
    issues.push(`${filename}: no \`revision: str = ...\` declaration`);
  } else if (declared[1] !== fromName) {
    issues.push(
      `${filename}: filename revision "${fromName}" != declared revision "${declared[1]}"` +
        " — `alembic downgrade <rev>` takes the declared one, so they must agree",
    );
  }

  const order = METADATA_FIELDS.map((field) => content.indexOf(`\n${field}:`)).filter((i) => i >= 0);
  if (order.length !== METADATA_FIELDS.length) {
    issues.push(`${filename}: metadata block must declare ${METADATA_FIELDS.join(", ")}`);
  } else if (order.some((position, index) => index > 0 && position < order[index - 1])) {
    issues.push(`${filename}: metadata block out of order — ${METADATA_FIELDS.join(" -> ")}`);
  }

  const upgrade = /\ndef upgrade\(\) -> None:\n([\s\S]*?)(?=\ndef |$)/.exec(content);
  const downgrade = /\ndef downgrade\(\) -> None:\n([\s\S]*?)(?=\ndef |$)/.exec(content);
  if (upgrade === null) issues.push(`${filename}: no \`upgrade()\``);
  if (downgrade === null) {
    issues.push(`${filename}: no \`downgrade()\` — every revision declares its reverse`);
  } else {
    const body = downgrade[1]
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line !== "" && !line.startsWith("#"));
    const inert = body.length === 0 || body.every((line) => line === "pass" || /^"""/.test(line));
    if (inert) {
      issues.push(
        `${filename}: \`downgrade()\` is a silent no-op — reverse the change, or ` +
          "`raise NotImplementedError(<reason>)` so a downgrade fails instead of lying",
      );
    }
  }
  if (upgrade !== null) {
    const upgradeBody = upgrade[1]
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line !== "" && !line.startsWith("#"));
    const upgradeInert = upgradeBody.length === 0 || upgradeBody.every((line) => line === "pass" || /^"""/.test(line));
    if (upgradeInert) {
      issues.push(
        `${filename}: \`upgrade()\` is a no-op — an empty autogenerate means the schema ` +
          "already matches; delete the revision instead of keeping an empty history entry",
      );
    }
  }

  if (!content.endsWith("\n")) {
    issues.push(`${filename}: no final newline — the last line is not a line`);
  } else if (content.endsWith("\n\n")) {
    issues.push(`${filename}: blank line at end of file — keep exactly one final newline`);
  }

  const firstFunction = content.search(/^def /m);
  for (const match of content.matchAll(/^([A-Za-z_][A-Za-z0-9_]*)(?::[^=\n]+)?\s*=/gm)) {
    const [, name] = match;
    if (METADATA_FIELDS.includes(name)) continue;
    if (name !== name.toUpperCase()) {
      issues.push(`${filename}: module constant \`${name}\` must be UPPER_SNAKE_CASE`);
    }
    if (firstFunction >= 0 && (match.index ?? 0) > firstFunction) {
      issues.push(`${filename}: module constant \`${name}\` declared after the first function`);
    }
  }

  return issues;
}

export function checkMigrationPolicy(): string[] {
  if (!existsSync(versionsDir)) return [];

  const upstream = getUpstream();
  const state = upstream === null ? null : upstreamState(upstream);

  const issues: string[] = [];
  for (const filename of readdirSync(versionsDir)) {
    if (!filename.endsWith(".py")) continue;
    if (isGrandfatheredMigration(filename)) continue;

    const path = join(versionsDir, filename);
    const content = readFileSync(path, "utf-8");
    const tables = extractTables(content);
    const touchesIntegrationTable = [...tables].some((table) => table.startsWith("integration_"));
    const declaresIntegrationMigration = filename.includes("_integration_");
    if (touchesIntegrationTable && !declaresIntegrationMigration) {
      issues.push(`${filename}: integration-table migration filename must include _integration_`);
    }
    if (declaresIntegrationMigration && !touchesIntegrationTable) {
      issues.push(`${filename}: _integration_ filename must target an integration_* table`);
    }

    const relativePath = `backend/alembic/versions/${filename}`;
    if (state !== null && state.pushed.has(relativePath)) {
      if (state.modified.has(relativePath)) {
        issues.push(`${filename}: pushed migration is immutable — create a new revision instead`);
      }
      continue;
    }

    // Layout is checked here, below the immutability gate: a pushed revision
    // cannot be reshaped without rewriting applied history, so the standard
    // binds the revisions still being written.
    issues.push(...checkMigrationLayout(filename, content));

    if (/\bop\.execute\b/.test(content)) {
      issues.push(`${filename}: unpushed migration uses unscoped raw operations`);
      continue;
    }

    // Schema and data migrations both target exactly one table. `table(...)`
    // declarations make a bulk seed's target explicit to this checker.
    if (tables.size !== 1) {
      issues.push(
        `${filename}: unpushed migration must target exactly one table (found ${tables.size || "none"})`,
      );
    }
  }

  return issues;
}

function getUpstream(): string | null {
  const result = spawnSync("git", ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], {
    cwd: projectRoot,
    encoding: "utf-8",
  });
  return result.status === 0 ? result.stdout.trim() : null;
}

/**
 * Which migrations exist upstream, and which of those differ from the working
 * tree — two set queries instead of one `git show` per file. The per-file form
 * spawned 51 git processes and measured ~470ms on every mutating tool result.
 * Keyed by the upstream commit, so a push invalidates it immediately.
 */
function upstreamState(upstream: string): { pushed: Set<string>; modified: Set<string> } {
  const head = spawnSync("git", ["rev-parse", upstream], { cwd: projectRoot, encoding: "utf-8" });
  const key = `${upstream}@${head.status === 0 ? head.stdout.trim() : "unknown"}`;
  const cached = upstreamCache.get(key);
  if (cached !== undefined) return cached;

  const listed = spawnSync(
    "git",
    ["ls-tree", "-r", "--name-only", upstream, "--", MIGRATIONS_PATH],
    { cwd: projectRoot, encoding: "utf-8" },
  );
  const changed = spawnSync(
    "git",
    ["diff", "--name-only", upstream, "--", MIGRATIONS_PATH],
    { cwd: projectRoot, encoding: "utf-8" },
  );
  const state = {
    pushed: new Set(splitLines(listed.status === 0 ? listed.stdout : "")),
    modified: new Set(splitLines(changed.status === 0 ? changed.stdout : "")),
  };
  upstreamCache.set(key, state);
  return state;
}

function splitLines(output: string): string[] {
  return output.split("\n").map((line: string) => line.trim()).filter(Boolean);
}

function extractTables(content: string): Set<string> {
  const tables = new Set<string>();
  for (const pattern of TABLE_PATTERNS) {
    for (const match of content.matchAll(pattern)) {
      tables.add(match[1]);
    }
  }
  return tables;
}
