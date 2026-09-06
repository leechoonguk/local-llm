// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { layerFiles } from "./backend-layout.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { resolveProjectRoot } from "./hook-project-root.ts";

/**
 * Domain structure checks — 5-layer CRUD pattern (backend-domain.md).
 *
 * Validates:
 *   - model filename format (<name>.py, lowercase alphanumeric)
 *   - data chain existence (model → schema → repository → service; router optional)
 *   - file contents per layer (model/schema/repository/service/router/DI/main/env)
 *   - the schema layer's public surface (Pydantic classes + to_read/to_read_list)
 *   - no generic `find_stale` finder (retention is per-domain, by its own column)
 *
 * Pure validation — no ast-grep, no side effects. Called by the
 * check-backend-domain orchestrator.
 */

const projectRoot = resolveProjectRoot();

/**
 * The only module-level functions a schema module may expose.
 *
 * Not a style list: these two are the layer's documented surface
 * (backend-domain.md), and every other public function in `schemas/` is logic
 * that belongs to whoever calls it.
 */
const SCHEMA_PUBLIC_FUNCTIONS = new Set(["to_read", "to_read_list"]);

/**
 * A schema module exposes its Pydantic classes and nothing else but
 * `to_read`/`to_read_list`.
 *
 * Measured on this repository: a ledger domain grew two public functions in
 * `schemas/` — one building a request object out of an external API record,
 * one normalising a timestamp a driver had handed back naive. Both were
 * imported by the service, both passed every gate, and neither belonged to the
 * schema layer: the first is a constructor of the class it returns, the second
 * is a comparison detail of the caller. The reason they landed there is
 * mechanical, not careless — `domain/service-method-async.yml` forbids a sync
 * `def` anywhere in `services/`, so `schemas/` is the nearest place a helper
 * compiles, and nothing was watching it.
 *
 * The fix a violation names is therefore concrete: put a constructor on the
 * class (`<Class>.from_record`), and keep a caller's detail in the caller.
 */
/**
 * `user` → `User`, `food_barcode` → `FoodBarcode`.
 *
 * Capitalising the first letter alone was enough while every flat domain was one
 * word: the first two-word table (`food_barcode`, the first of five sibling
 * ledgers from one provider) made this check demand a class called
 * `Food_barcode`, which no Python file would ever be allowed to declare.
 */
/**
 * One entry per schema file: `[leaf, source]`, with `null` for a flat domain.
 *
 * The families a file may declare depend on which leaf it is, so the check
 * reads the files apart rather than through `readLayerSource`'s concatenation.
 */
function schemaLeafSources(schemaDir: string, name: string): [string | null, string][] {
  const flat = join(schemaDir, `${name}.py`);
  if (existsSync(flat)) return [[null, readFileSync(flat, "utf-8")]];
  const folder = join(schemaDir, name);
  if (!existsSync(folder)) return [];
  return readdirSync(folder)
    .filter((file: string) => file.endsWith(".py") && file !== "__init__.py")
    .sort()
    .map((file: string): [string | null, string] => [
      file.replace(/\.py$/, ""),
      readFileSync(join(folder, file), "utf-8"),
    ]);
}

/**
 * The tables of a domain that a batch job fills from a provider - one per
 * `app/batch/sync_<name>_<table>_ledger.py`. The job's name carries the table
 * it fills (`check-backend-batch`), so the file is the fact, not a marker; a
 * domain with none is not a ledger domain.
 */
function ledgerTablesOf(base: string, name: string): string[] {
  const batchDir = join(base, "batch");
  if (!existsSync(batchDir)) return [];
  const tables: string[] = [];
  for (const file of readdirSync(batchDir)) {
    const m = new RegExp(`^sync_${name}_([a-z0-9_]+)_ledger\\.py$`).exec(file);
    if (m !== null) tables.push(m[1]);
  }
  return tables;
}

function pascalCase(domain: string): string {
  return domain
    .split("_")
    .map((part: string) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

export function checkSchemaSurface(base: string): string[] {
  const issues: string[] = [];
  const schemaDir = join(base, "schemas");
  if (!existsSync(schemaDir)) return issues;

  for (const file of layerFiles(schemaDir)) {
    const source = readFileSync(join(schemaDir, file), "utf-8");
    for (const declaration of source.matchAll(/^(?:async )?def (\w+)\(/gm)) {
      const name = declaration[1];
      if (name.startsWith("_") || SCHEMA_PUBLIC_FUNCTIONS.has(name)) continue;
      issues.push(
        `schemas/${file}: \`${name}()\` is a public function in the schema layer — ` +
          "its surface is the Pydantic classes plus to_read/to_read_list. Put a " +
          "constructor on the class it builds (`<Class>.from_record`), keep a " +
          "caller's detail in the caller, or make it module-private (`_name`)",
      );
    }
  }
  return issues;
}

/**
 * Under asyncio there is no safe lazy default: a relationship touched outside a
 * loaded query raises `MissingGreenlet` from deep inside greenlet plumbing, at
 * whichever endpoint happens to touch it first. `lazy="raise_on_sql"` moves that
 * failure to the access itself with a sentence a reader can act on, and makes
 * the eager-load contract enforceable by the runtime instead of by review.
 */
/**
 * `find_stale` is banned by name, in every repository and service.
 *
 * It used to be the template: every repository had to define it and had to
 * filter `created_at < older_than`. Measured across the tree the day it was
 * removed: fourteen definitions, zero business callers — pure scaffolding —
 * and the one blanket semantic was wrong for every table that has a real
 * retention story. A user is stale by last activity, a token by its own
 * expiry (`find_expired`/`expires_at`), a run by when it finished
 * (`find_finished_before`/`finished_at`). Purging any of them by creation
 * date deletes active rows.
 *
 * So a retention finder is named for its semantic and its column, and exists
 * only where something calls it. A master table gets none.
 */
export function checkNoGenericStaleFinder(base: string): string[] {
  const issues: string[] = [];
  for (const layer of ["repositories", "services"]) {
    const layerDir = join(base, layer);
    if (!existsSync(layerDir)) continue;
    for (const file of layerFiles(layerDir)) {
      const source = readFileSync(join(layerDir, file), "utf-8");
      const line = source.split("\n").findIndex((text: string) => text.includes("def find_stale("));
      if (line === -1) continue;
      issues.push(
        `${layer}/${file}:${line + 1}: \`find_stale\` is the retired blanket finder — name the ` +
          "semantic and its column (find_expired/expires_at, find_finished_before/finished_at), " +
          "and only where a caller exists; a created_at purge deletes active rows",
      );
    }
  }
  return issues;
}

export function checkRelationshipLoading(base: string): string[] {
  const issues: string[] = [];
  const modelsDir = join(base, "models");
  if (!existsSync(modelsDir)) return issues;

  // A folder domain's tables are one level down, and a relationship declared
  // there needs its `lazy=` policy just as much — under asyncio a forgotten
  // eager load is a MissingGreenlet in production, not a slow query.
  for (const file of layerFiles(modelsDir)) {
    const source = readFileSync(join(modelsDir, file), "utf-8");
    const lines = source.split("\n");
    lines.forEach((line: string, index: number) => {
      if (!/=\s*relationship\(/.test(line)) return;
      // The call may span lines; read to its closing parenthesis.
      let call = line;
      for (let next = index + 1; next < lines.length && !/\)\s*$/.test(call); next++) {
        call += `\n${lines[next]}`;
      }
      if (/lazy=/.test(call)) return;
      const name = (/^\s*(\w+)/.exec(line) ?? [])[1] ?? "relationship";
      issues.push(
        `models/${file}:${index + 1}: ${name} declares no \`lazy=\` policy — ` +
          'under asyncio use lazy="raise_on_sql" so a forgotten eager load fails at the ' +
          "access instead of raising MissingGreenlet in production",
      );
    });
  }
  return issues;
}

/**
 * A column's closed vocabulary survives into the schema that exposes it.
 *
 * `check-backend-table-design` already requires a short type/status/mode column
 * to carry `CheckConstraint("<col> IN (...)")`. That is where the vocabulary is
 * *decided*; this is where it is **kept**. A schema field that widens the column
 * back to `str` throws the set away at the only layer a client can read, and the
 * loss is silent in both directions — the server still refuses a bad value, so
 * nothing fails until a reader has to guess what the column can hold.
 *
 * The chain this closes: constraint → `Literal[...]` → (`check-frontend-types`,
 * which already maps a `Literal` to the same TS union) → the union a screen
 * switches on. Measured before it existed: `integration_field` kept its four
 * vocabularies through all three layers while `batch_run.status`,
 * `batch_run.trigger`, `batch_step.status`, `integration_call.method` and
 * `integration_call.outcome` were `str` in their schemas — and the TS side had
 * been narrowed by hand, answerable to nothing.
 *
 * Model file and schema file mirror by path (`models/batch/run.py` ↔
 * `schemas/batch/run.py`), which is what keeps a `status` on one table from being
 * compared against another table's.
 */
export function checkClosedVocabularyExposed(base: string): string[] {
  const issues: string[] = [];
  const modelsDir = join(base, "models");
  const schemasDir = join(base, "schemas");
  if (!existsSync(modelsDir) || !existsSync(schemasDir)) return issues;

  for (const relative of layerFiles(modelsDir)) {
    const source = readFileSync(join(modelsDir, relative), "utf-8");
    const schemaPath = join(schemasDir, relative);
    for (const [column, values] of closedValueSets(source)) {
      if (!existsSync(schemaPath)) continue;
      const schema = readFileSync(schemaPath, "utf-8");
      for (const annotation of fieldAnnotations(schema, column)) {
        const declared = literalValues(schema, annotation, base);
        if (declared === null) {
          issues.push(
            `schemas/${relative}: ${column}: ${annotation} widens a closed set back to a ` +
              `free string — the column accepts only ${values.join(", ")}, so declare a ` +
              "Literal alias and let the reader switch on it",
          );
          continue;
        }
        const missing = values.filter((value: string) => !declared.has(value));
        const extra = [...declared].filter((value: string) => !values.includes(value));
        if (missing.length === 0 && extra.length === 0) continue;
        issues.push(
          `schemas/${relative}: ${column} declares a Literal the constraint does not ` +
            `match — ${missing.length > 0 ? `missing ${missing.join(", ")}` : ""}` +
            `${missing.length > 0 && extra.length > 0 ? "; " : ""}` +
            `${extra.length > 0 ? `not in the constraint: ${extra.join(", ")}` : ""}`,
        );
      }
    }
  }
  return issues;
}

/**
 * An input the API accepts must fit the column that stores it.
 *
 * The frontend/backend length parity (`check-frontend-contract`) compares a form
 * against the schema. This is the layer below it, and its failure is worse: a
 * value the schema admits and the column cannot hold is not a 422, it is an
 * `IntegrityError` from the database — a 500 the user cannot act on and the log
 * reports as a server fault rather than bad input.
 *
 * Two ways to get there, and both are checked:
 *
 * - the schema caps higher than the column (`max_length=200` into `String(120)`);
 * - the schema does not cap at all, so any string reaches a bounded column.
 *
 * Only `*CreateRequest` / `*UpdateRequest` matter: those are the inputs. A read
 * response carries what the row already holds, so a bound there proves nothing.
 *
 * Model and schema mirror by path, the same correspondence the closed-vocabulary
 * check uses, which is what keeps one table's `code` from being measured against
 * another table's column.
 */
export function checkColumnLengthParity(base: string): string[] {
  // A field declared by both the create and the update request produces the
  // same sentence twice, and the fix is the one constant both read.
  const issues = new Set<string>();
  const modelsDir = join(base, "models");
  const schemasDir = join(base, "schemas");
  if (!existsSync(modelsDir) || !existsSync(schemasDir)) return [];

  for (const relative of layerFiles(modelsDir)) {
    const schemaPath = join(schemasDir, relative);
    if (!existsSync(schemaPath)) continue;
    const columns = stringColumns(readFileSync(join(modelsDir, relative), "utf-8"));
    if (columns.size === 0) continue;

    const schema = readFileSync(schemaPath, "utf-8");
    const constants = moduleConstants(schema);
    for (const [field, declaration] of requestStringFields(schema)) {
      const column = columns.get(field);
      if (column === undefined) continue;

      const capped = /\bmax_length\s*=\s*(\w+)/.exec(declaration);
      if (capped === null) {
        issues.add(
          `schemas/${relative}: ${field} accepts any length but the column is ` +
            `String(${column}) — an over-long value is refused by the database as a 500, ` +
            "not by the schema as a 422",
        );
        continue;
      }
      const declared = /^\d+$/.test(capped[1]) ? Number(capped[1]) : constants.get(capped[1]);
      if (declared === undefined || declared <= column) continue;
      issues.add(
        `schemas/${relative}: ${field} caps at ${declared} but the column is ` +
          `String(${column}) — the schema admits a value the database then refuses`,
      );
    }
  }
  return [...issues];
}

/** `<column> -> n` for every `mapped_column(String(n))`, module constants resolved. */
function stringColumns(model: string): Map<string, number> {
  const constants = moduleConstants(model);
  const found = new Map<string, number>();
  for (const match of model.matchAll(
    /^\s+(\w+):\s*Mapped\[[^\]]*\]\s*=\s*mapped_column\(([\s\S]{0,220}?)\)\n/gm,
  )) {
    const sized = /String\((\w+)\)/.exec(match[2]);
    if (sized === null) continue;
    const length = /^\d+$/.test(sized[1]) ? Number(sized[1]) : constants.get(sized[1]);
    if (length !== undefined) found.set(match[1], length);
  }
  return found;
}

/** `NAME = 120` module constants, the form `code-layout` requires for a literal. */
function moduleConstants(source: string): Map<string, number> {
  const found = new Map<string, number>();
  for (const match of source.matchAll(/^(\w+) = (\d+)$/gm)) {
    found.set(match[1], Number(match[2]));
  }
  return found;
}

/** Every string field of every request class, with the declaration it carries. */
function requestStringFields(schema: string): Array<[string, string]> {
  const found: Array<[string, string]> = [];
  for (const block of schema.matchAll(
    /class \w+(?:Create|Update)Request\([^)]*\):([\s\S]*?)(?=\nclass |\Z)/g,
  )) {
    let pending = "";
    for (const line of block[1].split("\n")) {
      if (/^\S/.test(line) && line.trim() !== "") break;
      pending = pending === "" ? line : `${pending} ${line.trim()}`;
      if (countParens(pending) > 0) continue;
      const declaration = pending;
      pending = "";
      const field = /^\s{4}(\w+)\s*:\s*([^\n=]+)/.exec(declaration);
      if (field === null || field[1] === "model_config") continue;
      if (!/\bstr\b/.test(field[2])) continue;
      found.push([field[1], declaration]);
    }
  }
  return found;
}

/** Unclosed parentheses in an accumulated declaration. */
function countParens(text: string): number {
  return (text.match(/\(/g) ?? []).length - (text.match(/\)/g) ?? []).length;
}

/** `<column> IN ('A', 'B')` check constraints, as `[column, values]`. */
function closedValueSets(source: string): Array<[string, string[]]> {
  const sets: Array<[string, string[]]> = [];
  for (const match of source.matchAll(/CheckConstraint\s*\(/g)) {
    const argument = parenthesized(source, match[0].length + match.index - 1);
    if (argument === null) continue;
    // The expression may be split across adjacent string literals.
    const expression = [...argument.matchAll(/"([^"]*)"/g)].map((part) => part[1]).join(" ");
    const column = /^\s*(\w+)\s+IN\s*\(/.exec(expression);
    if (column === null) continue;
    sets.push([column[1], [...expression.matchAll(/'([^']+)'/g)].map((value) => value[1])]);
  }
  return sets;
}

/** From an opening `(` to its match. */
function parenthesized(source: string, open: number): string | null {
  let depth = 0;
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === "(") depth += 1;
    else if (source[index] === ")") {
      depth -= 1;
      if (depth === 0) return source.slice(open, index + 1);
    }
  }
  return null;
}

/** Every `<column>: <annotation>` declared as a class field in the schema. */
function fieldAnnotations(schema: string, column: string): string[] {
  return [...schema.matchAll(new RegExp(`^\\s+${column}\\s*:\\s*([^\n=]+)`, "gm"))].map(
    (match) => match[1].trim().replace(/,$/, ""),
  );
}

/**
 * The values an annotation admits, or `null` when it admits any string.
 *
 * Resolves the three forms this repository uses: an inline `Literal[...]`, a
 * module-level alias assigned to one (`ResponseFormat = Literal["JSON", "XML"]`),
 * and an alias **imported** from the module that produces the values.
 *
 * The import form is not a loophole, it is the point: a vocabulary is spelled
 * once. `integration_call`'s verbs and outcomes are decided in
 * `core/integration.py`, where the literals are actually written, so the schema
 * imports them instead of restating them — and a check that only looked in the
 * schema file would have called that correct code a violation and pushed the
 * author into duplicating the set.
 */
function literalValues(schema: string, annotation: string, appBase: string): Set<string> | null {
  const bare = annotation.replace(/\|\s*None/, "").trim();
  const inline = /^Literal\[([\s\S]*)\]$/.exec(bare);
  if (inline !== null) return literalMembers(inline[1]);
  if (!/^[A-Z]\w*$/.test(bare)) return null;

  const local = new RegExp(`^${bare}\\s*=\\s*Literal\\[([\\s\\S]*?)\\]`, "m").exec(schema);
  if (local !== null) return literalMembers(local[1]);

  const imported = importedFrom(schema, bare);
  if (imported === null) return null;
  const module = join(appBase, `${imported.module.split(".").join("/")}.py`);
  if (!existsSync(module)) return null;
  const source = readFileSync(module, "utf-8");
  const alias = new RegExp(`^${imported.remoteName}\\s*=\\s*Literal\\[([\\s\\S]*?)\\]`, "m").exec(source);
  return alias === null ? null : literalMembers(alias[1]);
}

/** The quoted members of a `Literal[...]` body. */
function literalMembers(body: string): Set<string> {
  return new Set([...body.matchAll(/"([^"]+)"/g)].map((match) => match[1]));
}

/**
 * The `app.`-relative module a name is imported from, and the name it had
 * there — `import CallOutcome as OutcomeVocabulary` binds the local name to a
 * remote one, and resolving the local name in the remote module finds nothing.
 * Measured: the rename alone turned a correct schema into a "widens" report.
 */
function importedFrom(schema: string, name: string): { module: string; remoteName: string } | null {
  for (const match of schema.matchAll(/^from\s+app\.([\w.]+)\s+import\s+([^\n(]*)/gm)) {
    for (const item of match[2].split(",")) {
      const bound = /^\s*(\w+)(?:\s+as\s+(\w+))?\s*$/.exec(item);
      if (bound === null) continue;
      if ((bound[2] ?? bound[1]) === name) return { module: match[1], remoteName: bound[1] };
    }
  }
  return null;
}

/**
 * Domains that own more than one model file — a multi-table aggregate, checked
 * by its own file-shape hooks (check-backend-model-files,
 * check-backend-repository-files) and, when one exists, its dedicated
 * configuration hook, never by the generic single-resource CRUD template every
 * other hook in this file assumes.
 *
 * **Structural, not named.** Hardcoding a domain's name to skip it is what
 * broke three times in one session when `integration.py` became five files:
 * `check-backend-transaction`'s own `file !== "integration.py"` filter,
 * `check-backend-tests`'s own `Set(["integration"])`, and this file's earlier
 * `name === "integration"` skip all stopped matching anything the day the
 * split landed, because none of them asked "does this domain own more than one
 * file" — they asked "is this domain literally named integration". A domain
 * discovered this way needs no update when the next aggregate is split; a
 * hardcoded name needs one every time, silently, until someone happens to
 * touch that exact domain again.
 *
 * Measured two ways, because the aggregate has two shapes: several model files
 * (the folder), or one flat file declaring several tables — the shape a domain
 * has before its folder move, and the shape the sandbox baseline keeps.
 */
export function aggregateDomains(): Set<string> {
  const base = join(projectRoot, "backend", "app");
  const serviceDir = join(base, "services");
  if (!existsSync(join(base, "models")) || !existsSync(serviceDir)) return new Set();

  const result = new Set<string>();
  for (const name of listDomains(serviceDir)) {
    if (ownedModelFiles(name).length > 1 || ownedTableCount(name) > 1) result.add(name);
  }
  return result;
}

/**
 * The model files one domain owns, in either shape:
 *
 * - `models/<domain>/*.py` - a folder, required once a domain owns more than
 *   one table (`backend-model-files.md`). The file inside is named after its
 *   table with the domain prefix dropped, so `integration/provider.py` maps
 *   `integration_provider`.
 * - `models/<domain>.py`, or the flat `models/<domain>_*.py` a domain has
 *   while it is being moved into a folder.
 *
 * Returned as paths relative to `models/`, because a caller that only ever saw
 * bare filenames was the reason the folder move went unnoticed: five files
 * moved one directory down, `readdirSync` stopped matching them, and every
 * aggregate check silently reported success on nothing.
 */
export function ownedModelFiles(domain: string): string[] {
  const modelDir = join(projectRoot, "backend", "app", "models");
  if (!existsSync(modelDir)) return [];

  const folder = join(modelDir, domain);
  if (existsSync(folder) && statSync(folder).isDirectory()) {
    return readdirSync(folder)
      .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
      .map((f: string) => `${domain}/${f}`);
  }

  // layer-flat-ok: the folder shape is handled above; this is the flat fallback,
  // matching `<domain>.py` and `<domain>_*.py` at the layer root by construction.
  return readdirSync(modelDir).filter(
    (f: string) => f === `${domain}.py` || (f.startsWith(`${domain}_`) && f.endsWith(".py")),
  );
}

/**
 * `__tablename__` declarations across the model files one domain owns — the
 * other half of the aggregate measure. A flat `models/<domain>.py` that maps
 * four tables is exactly as much an aggregate as four files in a folder, and
 * the singular one-table templates fit it exactly as badly.
 */
export function ownedTableCount(domain: string): number {
  const modelDir = join(projectRoot, "backend", "app", "models");
  let count = 0;
  for (const file of ownedModelFiles(domain)) {
    const source = readFileSync(join(modelDir, file), "utf-8");
    count += (source.match(/^\s*__tablename__\s*=/gm) ?? []).length;
  }
  return count;
}

/** Domain names, from the layer that decides a domain exists: `services/`. */
export function listDomains(serviceDir: string): string[] {
  if (!existsSync(serviceDir)) return [];
  const names: string[] = [];
  for (const entry of readdirSync(serviceDir, { withFileTypes: true })) {
    if (entry.name === "__init__.py" || entry.name === "__pycache__") continue;
    if (entry.isDirectory()) names.push(entry.name);
    else if (entry.name.endsWith(".py")) names.push(entry.name.replace(".py", ""));
  }
  return names;
}

/** True when `stem` (a filename minus `.py`) belongs to a multi-file domain. */
export function belongsToAggregateDomain(stem: string, aggregates: Set<string>): boolean {
  for (const domain of aggregates) {
    if (stem === domain || stem.startsWith(`${domain}_`)) return true;
  }
  return false;
}


/**
 * One domain's source in a layer, as a single string: the file when the layer
 * holds `<domain>.py`, the concatenation of `<domain>/*.py` when the domain has
 * grown into a folder.
 *
 * Concatenating is what makes the split invisible to a content check. The
 * alternative - picking one file - is how a check starts reading half a
 * contract and passing: `schemas/integration/provider.py` alone has no
 * `IntegrationSecretCreateRequest`, and the domain's schema contract is the
 * whole folder.
 */
export function readLayerSource(layerDir: string, domain: string): string | null {
  const file = join(layerDir, `${domain}.py`);
  if (existsSync(file)) return readFileSync(file, "utf-8");

  const folder = join(layerDir, domain);
  if (!existsSync(folder) || !statSync(folder).isDirectory()) return null;
  return readdirSync(folder)
    .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
    .sort()
    .map((f: string) => readFileSync(join(folder, f), "utf-8"))
    .join("\n");
}

/**
 * Absolute paths of the files one domain owns in a layer - the folder's
 * contents, or the flat `<domain>.py` / `<domain>_*.py` files.
 */
export function listDomainLayerFiles(layerDir: string, domain: string): string[] {
  if (!existsSync(layerDir)) return [];

  const folder = join(layerDir, domain);
  if (existsSync(folder) && statSync(folder).isDirectory()) {
    return readdirSync(folder)
      .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
      .sort()
      .map((f: string) => join(folder, f));
  }

  return readdirSync(layerDir)
    .filter((f: string) => f === `${domain}.py` || (f.startsWith(`${domain}_`) && f.endsWith(".py")))
    .sort()
    .map((f: string) => join(layerDir, f));
}

/**
 * A layer must not hold both `<domain>.py` and `<domain>/` for the same domain.
 *
 * Measured: with `models/user.py` and `models/user/extra.py` both present,
 * every check passed. `ownedModelFiles()` answers with the folder and stops
 * looking, so the flat file's table was invisible - the exact shape a
 * half-finished move leaves behind, and the one state where "which files does
 * this domain own" has two answers.
 */
export function checkLayerOwnership(layerDir: string, layerLabel: string): string[] {
  if (!existsSync(layerDir)) return [];
  const issues: string[] = [];
  for (const entry of readdirSync(layerDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === "__pycache__") continue;
    if (!existsSync(join(layerDir, `${entry.name}.py`))) continue;
    issues.push(
      `${layerLabel}/: ${entry.name} owns both ${entry.name}.py and ${entry.name}/ - ` +
        "a domain lives in one or the other; finish the move and delete the flat file",
    );
  }
  return issues;
}

export function checkDomainStructure(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");
  const modelDir = join(base, "models");
  const schemaDir = join(base, "schemas");
  const repoDir = join(base, "repositories");
  const serviceDir = join(base, "services");
  const routerDir = join(base, "routers");
  const mainPy = join(base, "main.py");
  const envPy = join(projectRoot, "backend", "alembic", "env.py");

  if (!existsSync(modelDir)) {
    issues.push("backend/app/models/ directory not found");
    return issues;
  }

  // No layer may answer "which files does this domain own" two ways at once.
  for (const [dir, label] of [
    [modelDir, "models"],
    [schemaDir, "schemas"],
    [repoDir, "repositories"],
    [serviceDir, "services"],
  ] as const) {
    issues.push(...checkLayerOwnership(dir, label));
  }

  // A domain is a 5-layer stack, and the layer that decides one exists is the
  // service. Discovery used to enumerate **model files**, which made a table
  // and a domain the same thing - so `integration` had to be skipped by name,
  // and the moment one table moved to its own file the checker demanded a
  // router, a schema and a service for `integration_secret`.
  //
  // One table per model file is the table rule (`backend-model-files.md`), and
  // a domain that owns several of them keeps them in `models/<domain>/`. Both
  // shapes are read through `ownedModelFiles()` so this checker, the aggregate
  // predicate, and the file-shape hooks cannot disagree about what a domain
  // owns - they disagreed once already, and the answer was silence.
  const modelFiles: string[] = layerFiles(modelDir);

  // File naming: lower snake case, because a model file is named after its
  // table (minus the domain prefix when it sits in the domain's folder).
  for (const modelFile of modelFiles) {
    const name = modelFile.replace(/^.*\//, "").replace(".py", "");
    if (!/^[a-z][a-z0-9_]*$/.test(name)) {
      issues.push(
        `${modelFile}: model filename must be lower snake case - it is named after ` +
          "the table it maps (backend-model-files.md)",
      );
    }
  }

  const domains: string[] = listDomains(serviceDir);

  const repoFiles: string[] = existsSync(repoDir) ? layerFiles(repoDir) : [];

  for (const name of domains) {
    const cls = pascalCase(name);

    const owned = ownedModelFiles(name);
    if (owned.length === 0) {
      issues.push(
        `${name}: services layer exists but no model file ` +
          `(models/${name}.py, models/${name}/*.py, or models/${name}_*.py)`,
      );
      continue;
    }
    const modelFile = owned.includes(`${name}.py`) ? `${name}.py` : owned.sort()[0];
    // A model file per table (backend-model-files.md), so a domain's repository
    // side is not required to be exactly `repositories/<name>.py` either - only
    // that at least one file exists for it, in the folder when there are
    // several (`backend-repository-files.md`).
    const ownedRepos = repoFiles.filter(
      (file: string) =>
        file === `${name}.py` || file.startsWith(`${name}_`) || file.startsWith(`${name}/`),
    );
    // The singular templates below (model class == domain name, repository's
    // 7-method shape) describe one table's worth of CRUD. A domain that owns
    // several files — several tables, several repositories — is checked by its
    // own file-shape hooks (check-backend-model-files,
    // check-backend-repository-files) and its dedicated configuration hook when
    // one exists; running the singular template against an arbitrarily chosen
    // file here is what let `models/integration_call.py` satisfy `model class
    // "Integration" not found` by prefix coincidence (`IntegrationCall` starts
    // with `Integration`) before this gate existed.
    // The aggregate is measured, never named (see aggregateDomains): several
    // model files, or one flat file declaring several tables. Either shape puts
    // the domain outside the one-table templates below.
    const isAggregate = owned.length > 1 || ownedTableCount(name) > 1;
    const isSingleFileDomain = !isAggregate && owned.length === 1 && owned[0] === `${name}.py`;
    const isSingleRepoDomain = !isAggregate && ownedRepos.length === 1 && ownedRepos[0] === `${name}.py`;

    // Data chain: model → schema → repository → service. Router is OPTIONAL —
    // a domain may be internal-only (batch jobs) or exposed via a custom
    // router (auth). When a router exists, its content is validated below.
    //
    // 완성도 요구는 **의존 방향으로만** 건다(2026-08-29 사용자 지적 + 실측). 도메인 발견 자체가
    // services/ 앵커라서 모델만(또는 모델+스키마만) 있는 상태는 도메인으로 잡히지 않는다 — 작업의
    // 첫 걸음에서 마지막 걸음을 요구하지 않는다. 여기 도달한 도메인은 서비스(또는 라우터)가 이미
    // 섰으므로 그 하류가 상류(schema·repository)를 요구한다. 완성 시점의 계약은 그대로다.
    const routerPath = join(routerDir, `${name}.py`);
    const hasRouter = existsSync(routerPath);
    const anchor = hasRouter ? "routers" : "services";
    const schemaSource = readLayerSource(schemaDir, name);
    if (schemaSource === null) {
      issues.push(
        `${name}: ${anchor} layer exists but schema layer is missing ` +
          `(schemas/${name}.py or schemas/${name}/*.py)`,
      );
    }
    if (ownedRepos.length === 0) {
      issues.push(
        `${name}: ${anchor} layer exists but repository layer is missing ` +
          `(repositories/${name}.py, repositories/${name}/*.py, or repositories/${name}_*.py)`,
      );
    }
    if (readLayerSource(serviceDir, name) === null) {
      // premature-ok: services/ 가 이 도메인을 선언했는데 읽을 소스가 없다 — 어느 단계에서든 결함이다.
      issues.push(`${name}: missing service file (services/${name}.py or services/${name}/*.py)`);
    }

    // --- Validate file contents ---

    const modelPath = join(modelDir, modelFile);
    const modelContent = readFileSync(modelPath, "utf-8");

    if (isSingleFileDomain) {
      // Model: should have Base, AuditMixin, UUID id, name/description
      if (!modelContent.includes("AuditMixin")) {
        issues.push(`${name}: model missing AuditMixin`);
      }
      if (!modelContent.includes("class " + cls)) {
        issues.push(`${name}: model class "${cls}" not found`);
      }
      if (!modelContent.includes("Mapped[uuid.UUID]")) {
        issues.push(`${name}: model id must be Mapped[uuid.UUID] (UUID primary key)`);
      }
      if (!modelContent.includes("default=uuid4")) {
        issues.push(`${name}: model id missing default=uuid4`);
      }
      if (!modelContent.includes("mapped_column")) {
        issues.push(`${name}: model missing mapped_column`);
      }
      if (!new RegExp(`__tablename__ = "${name}"`).test(modelContent)) {
        issues.push(`${name}: ${modelFile} must declare __tablename__ "${name}"`);
      }
    }

    // Schema: should have 6 classes, extra="forbid"
    // Naming convention: XBase, XCreateRequest, XCreateInternal, XReadResponse,
    // XUpdateRequest, XUpdateInternal (Request/Response suffixes).
    if (schemaSource !== null) {
      const schemaContent = schemaSource;
      /**
       * The class family, which is the domain's own name **or a leaf's**.
       *
       * A single-file domain has one entity, so the family is `<Domain>*`. A
       * folder domain need not: `food` is two sibling ledgers with no root
       * between them (`FoodBarcode*`, `FoodRawMaterial*`), and demanding
       * `FoodBase` would invent an entity nothing stores. `integration` passes
       * either way — its aggregate root happens to carry the domain's own name
       * while `IntegrationSecret*` and `IntegrationOperation*` are leaves — and
       * that coincidence is what made "one domain, one root" look like a rule.
       *
       * The domain's own name stays in the list for the root that may exist —
       * `integration/provider.py` declares `IntegrationCreateRequest`, not
       * `IntegrationProviderCreateRequest` — so both shapes pass and neither is
       * mandatory.
       */
      /**
       * A `<Family>Base` is the promise of a CRUD family, and the other five
       * are the rest of it.
       *
       * The family's name is the domain's own or a leaf's: `integration/
       * provider.py` declares `Integration*` while `food` — two sibling ledgers
       * with no root between them — declares `FoodBarcode*` and
       * `FoodRawMaterial*` and no `Food*` at all. Nested aggregates carry only
       * what they need (`IntegrationSecretCreateRequest` with no `Base`), and
       * the `Base` is exactly what tells the two apart.
       *
       * Checked per file, because a family is complete or it is not: against the
       * folder's concatenated text a sibling's `FoodBarcodeUpdateInternal`
       * answered for the `raw_material` leaf that had lost its own - measured,
       * on a planted deletion this check reported nothing.
       */
      const suffixes = [
        "CreateRequest",
        "CreateInternal",
        "ReadResponse",
        "UpdateRequest",
        "UpdateInternal",
      ];
      let complete = 0;
      for (const [leaf, source] of schemaLeafSources(schemaDir, name)) {
        const families = leaf === null ? [cls] : [cls, `${cls}${pascalCase(leaf)}`];
        const where = leaf === null ? `schemas/${name}.py` : `schemas/${name}/${leaf}.py`;
        for (const family of families) {
          if (!new RegExp(`class\\s+${family}Base\\b`).test(source)) continue;
          const missing = suffixes.filter(
            (suffix) => !new RegExp(`class\\s+${family}${suffix}\\b`).test(source),
          );
          if (missing.length === 0) complete += 1;
          else {
            issues.push(
              `${name}: ${where} declares ${family}Base but not ` +
                missing.map((suffix) => `${family}${suffix}`).join(", "),
            );
          }
        }
      }
      if (complete === 0) {
        issues.push(
          `${name}: no schema declares a complete class family - one file owes ` +
            `${cls}Base plus ${suffixes.map((suffix) => cls + suffix).join(", ")}, ` +
            "under the domain's name or a leaf's",
        );
      }

      // Every Read response exposes the optimistic-lock revision its caller holds:
      // a client that cannot see `version` cannot know which row it edited, and
      // its next write is either a blind overwrite or a 409 it cannot explain.
      // Stated for every table in backend-table-design.md; enforced only for
      // `integration` until a planted omission on a food ledger stayed green.
      for (const [leaf, source] of schemaLeafSources(schemaDir, name)) {
        for (const declaration of source.matchAll(
          /^class\s+(\w+ReadResponse)\((?:BaseModel|\w+)\):\n((?:[ \t].*\n|\n)*)/gm,
        )) {
          if (/^\s+version:\s*int\b/m.test(declaration[2])) continue;
          const where = leaf === null ? `schemas/${name}.py` : `schemas/${name}/${leaf}.py`;
          issues.push(
            `${name}: ${where}: ${declaration[1]} does not expose version: int - the ` +
              "optimistic-lock revision is part of every Read response (backend-table-design.md)",
          );
        }
      }

      // Per class, not per file: one new schema class without extra="forbid"
      // silently accepts unknown request fields while its siblings reject them.
      for (const declaration of schemaContent.matchAll(
        /^class\s+(\w+)\((?:BaseModel|\w+)\):\n((?:[ \t].*\n|\n)*)/gm,
      )) {
        const [, className, classBody] = declaration;
        if (!/model_config\s*=\s*ConfigDict\(/.test(classBody)) continue;
        if (!/extra=["']forbid["']/.test(classBody)) {
          issues.push(`${name}: schema class ${className} missing extra="forbid"`);
        }
      }
      if (!schemaContent.includes("from_attributes=True")) {
        issues.push(`${name}: schema Read missing from_attributes=True`);
      }
      if (!schemaContent.includes("def to_read(") || !schemaContent.includes("def to_read_list(")) {
        issues.push(`${name}: schema missing to_read()/to_read_list() helpers`);
      }
      if (!schemaContent.includes("id: UUID")) {
        issues.push(`${name}: schema Read missing id: UUID`);
      }
    }

    // Repository: should have 7 methods, UUID id params — the single-table
    // template. A domain with several repository files is checked structurally
    // by check-backend-repository-files instead (backend-repository-files.md).
    const repoPath = join(repoDir, `${name}.py`);
    if (isSingleRepoDomain && existsSync(repoPath)) {
      const repoContent = readFileSync(repoPath, "utf-8");
      const methods = ["async def get", "async def list", "async def create", "async def update", "async def delete", "def __init__"];
      for (const method of methods) {
        if (!repoContent.includes(method)) {
          issues.push(`${name}: repository missing method "${method.replace("async def ", "").replace("def ", "")}"`);
        }
      }
      if (!repoContent.includes(`${name}_id: UUID`)) {
        issues.push(`${name}: repository id params must be typed UUID (${name}_id: UUID)`);
      }
    }

    // Service: should have session.begin() transaction management and NotFoundError
    const servicePath = join(serviceDir, `${name}.py`);
    if (existsSync(servicePath)) {
      const serviceContent = readFileSync(servicePath, "utf-8");
      if (!serviceContent.includes("session.begin()")) {
        issues.push(`${name}: service missing session.begin() transaction management`);
      }
      if (!serviceContent.includes("NotFoundError")) {
        issues.push(`${name}: service missing NotFoundError`);
      }
      if (!serviceContent.includes(`${name}_id: UUID`)) {
        issues.push(`${name}: service id params must be typed UUID (${name}_id: UUID)`);
      }
      if (!serviceContent.includes("exclude_unset=True")) {
        issues.push(`${name}: service update must use exclude_unset=True`);
      }
      // `updated_at` belongs to the repository, set before its flush. A service
      // assignment lands after the flush and costs a second UPDATE, which bumps
      // the optimistic-lock version twice per request.
      if (/\.updated_at\s*=/.test(serviceContent)) {
        issues.push(
          `${name}: service must not assign updated_at — set it in the repository ` +
            "before flush (a post-flush assignment costs a second UPDATE and version bump)",
        );
      }
    }

    // Router: the CRUD template has 5 endpoints and UUID path params. A
    // **ledger domain** - one whose tables a batch job fills from a provider
    // (`app/batch/sync_<name>_*_ledger.py`) - is read-only instead: a row
    // written by hand is compared against the provider's record on the next
    // pass and overwritten, so a write endpoint there is a lie the sync corrects
    // nightly. The check refuses the write verbs rather than requiring them.
    if (hasRouter) {
      const routerContent = readFileSync(routerPath, "utf-8");
      const ledgerTables = ledgerTablesOf(base, name);
      const ledger = ledgerTables.length > 0;
      if (ledger) {
        // Per table, not per domain: a domain may hold a ledger beside a table
        // people edit, and only the ledger's paths refuse the write verbs. A
        // write route is held to the table its first path segment names
        // (`/raw-material/` -> `raw_material`); on a flat ledger domain every
        // route is the ledger's.
        for (const route of routerContent.matchAll(/@router\.(post|patch|put|delete)\("([^"]*)"/g)) {
          const leaf = route[2].split("/").filter((p: string) => p !== "" && !p.startsWith("{"))[0];
          const table = leaf === undefined ? name : leaf.replace(/-/g, "_");
          if (!ledgerTables.includes(table) && leaf !== undefined) continue;
          issues.push(
            `${name}: ${route[1].toUpperCase()} ${route[2]} writes the ${table} ledger - a batch ` +
              "job fills it from the provider and overwrites a hand-written row on its next pass",
          );
        }
      } else {
        if (!routerContent.includes("@router.post")) {
          issues.push(`${name}: router missing POST endpoint`);
        }
        // update 메서드는 스키마 의미가 정한다(PATCH=부분 갱신 / PUT=전체 교체) — 어느 쪽인지의
        // 판정은 check-backend-api-http 의 expectedUpdateMethod 소관이고, 여기서는 존재만 본다.
        if (!routerContent.includes("@router.patch") && !routerContent.includes("@router.put")) {
          issues.push(`${name}: router missing update endpoint (PATCH or PUT — the verb follows the update schema, rule://backend-api-http)`);
        }
        if (!routerContent.includes("@router.delete")) {
          issues.push(`${name}: router missing DELETE endpoint`);
        }
      }
      if (!routerContent.includes("@router.get")) {
        issues.push(`${name}: router missing GET endpoint`);
      }
      // A flat domain's row is `<name>_id`; a folder domain's row belongs to a
      // leaf, and `food_id` would name none of `food`'s four tables. The service
      // already spells it `food_raw_material_id`, so the router matches.
      const idParam = new RegExp(`\\b${name}(?:_[a-z0-9_]+)?_id: UUID`);
      // Only where a path carries an id: a ledger that publishes its page and
      // nothing by id has no parameter to type.
      const hasIdPath = /@router\.\w+\("[^"]*\{/.test(routerContent);
      if (hasIdPath && !idParam.test(routerContent)) {
        issues.push(
          `${name}: router path params must be typed UUID (${name}_id: UUID, or ` +
            `${name}_<leaf>_id: UUID on a folder domain)`,
        );
      }
      if (!routerContent.includes(`prefix="/${name}"`)) {
        issues.push(`${name}: router prefix must be "/${name}" (lowercase domain name)`);
      }
    }

    // Env: every one of the domain's model files must be imported. Per file, not
    // per domain: a table nobody imports is absent from the metadata, so
    // autogenerate writes an empty migration and the table never exists.
    if (existsSync(envPy)) {
      const envContent = readFileSync(envPy, "utf-8");
      for (const file of owned) {
        // `integration/provider.py` is the module `integration.provider`: the
        // folder is a package, so the import path carries a dot, not a slash.
        // `[\w(]` accepts the parenthesized multi-line form a four-table flat
        // module imports with — `import (` is as much a registration as `import X`.
        const module = file.replace(/\.py$/, "").split("/").join(".");
        if (!new RegExp(`from app\\.models\\.${module} import\\s*[\\w(]`).test(envContent)) {
          // premature-ok: autogenerate 는 import 없는 모델을 보지 못한다 — 이 등록은 모델 자체의 속성이다.
          issues.push(`${module}: not imported in alembic/env.py`);
        }
      }
    }

    // Main: 라우터 등록은 **라우터 파일이 생긴 뒤**에만 요구한다(2026-08-29).
    // 모델만 만든 상태에서 "router not included" 를 띄우는 것은 첫 걸음에서 마지막 걸음을 요구하는 것이다.
    if (hasRouter && existsSync(mainPy)) {
      const mainContent = readFileSync(mainPy, "utf-8");
      const routerRegistration = new RegExp(`include_router\\(${name}\\.router(?:,|\\))`);
      if (!routerRegistration.test(mainContent)) {
        issues.push(`${name}: router not included in main.py`);
      }
    }

    // Dependencies: service DI must exist (SessionDep -> ServiceDep). A domain
    // whose service layer is a folder has one service per file, so it needs one
    // factory and one Annotated alias per file - not one named after the domain,
    // which no longer exists as a class once the service is split.
    //
    // Required **only where a router exists**, because an `Annotated[X,
    // Depends(...)]` alias has exactly one consumer: an endpoint signature.
    // Demanded of a router-less domain it produced guaranteed dead code -
    // measured: `barcode` and `batch_checkpoint` are reached only by a batch
    // job, which constructs `Service(session)` itself (rule://backend-batch),
    // and their two aliases sat unused while this rule insisted on them.
    const depsServicesPath = join(base, "dependencies", "services.py");
    if (existsSync(depsServicesPath)) {
      const depsContent = readFileSync(depsServicesPath, "utf-8");
      const serviceFiles = listDomainLayerFiles(serviceDir, name);
      const isFolder = serviceFiles.some((file) => file.includes(`${name}/`));
      const parts = isFolder
        ? serviceFiles.map((file) => {
            const leaf = (file.split("/").pop() ?? "").replace(/\.py$/, "");
            const leafCls = pascalCase(leaf);
            return { factory: `get_${name}_${leaf}_service`, cls: `${cls}${leafCls}Service` };
          })
        : [{ factory: `get_${name}_service`, cls: `${cls}Service` }];
      const routerContent = hasRouter ? readFileSync(routerPath, "utf-8") : "";
      for (const part of parts) {
        // Required of the services an endpoint injects, not of every service
        // that exists. An `Annotated[X, Depends(...)]` alias has exactly one
        // consumer — an endpoint signature — so demanding one for a service no
        // router mentions produces guaranteed dead code, and did: `barcode`
        // (no router at all) and `batch_checkpoint` (a leaf of a domain whose
        // router publishes the other three) each carried an alias nothing
        // injected, kept alive by this rule. `check-backend-contract` owns the
        // other direction, so the pair reads: declare exactly the aliases your
        // endpoints use.
        if (!routerContent.includes(part.cls)) continue;
        if (!depsContent.includes(part.factory)) {
          issues.push(`${name}: missing ${part.factory} in dependencies/services.py`);
        }
        if (!new RegExp(`${part.cls}Dep\\s*=\\s*Annotated\\[\\s*${part.cls}`).test(depsContent)) {
          issues.push(`${name}: missing ${part.cls}Dep Annotated DI in dependencies/services.py`);
        }
      }
    } else {
      // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
      issues.push(`${name}: dependencies/services.py not found`);
    }
  }

  return issues;
}
