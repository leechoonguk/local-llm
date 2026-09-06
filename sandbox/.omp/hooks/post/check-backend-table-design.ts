/**
 * Check-Backend-Table-Design Post Hook
 *
 * After tool execution, validates the table design invariants in
 * .omp/rules/backend-table-design.md against backend/app/models/*.py:
 *   1. __tablename__ present, lower snake case, singular
 *   2. Primary key declared
 *   3. AuditMixin inherited
 *   4. Atomicity (1NF) — no numbered repeating-group columns
 *   5. Booleans not nullable
 *   6. DateTime columns are timezone-aware
 *   7. Foreign keys: _id suffix, explicit ondelete=, index=True
 *   8. Closed-value-set columns carry an IN (...) check constraint
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { layerFiles } from "../lib/backend-layout.ts";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";

const projectRoot = resolveProjectRoot();
const modelsDir = join(projectRoot, "backend", "app", "models");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */

/**
 * Columns whose name marks a closed value set. A short bounded String with one
 * of these suffixes must be constrained; longer strings are free-form media or
 * content types and are exempt.
 */
const CLOSED_SET_SUFFIX = /_(type|status|mode|format|source|kind|direction)$/;
const CLOSED_SET_MAX_LENGTH = 32;

export default function checkBackendTableDesign(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-table-design", event, () => {
    // Skip read-only tools — they cannot change model files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendTableDesignSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-table-design"); // resolved — allow re-warning
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-table-design",
      issues,
      "run make check-backend-table-design for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-table-design") };
  }));
}

/** One `name: Mapped[type] = mapped_column(args)` declaration. */
interface Column {
  name: string;
  type: string;
  args: string;
}

function checkBackendTableDesignSync(): string[] {
  if (!existsSync(modelsDir)) return ["backend/app/models/ not found"];

  const issues: string[] = [];
  // `listModelFiles` descends one level, which is the whole convention: a domain
  // that grew into a folder keeps its tables there. A bare `readdirSync` filtered
  // on `.py` skipped every directory, so nine of thirteen models — every table in
  // `batch/` and `integration/` — were never checked. Measured: `String` without
  // a length fired on `user.py` and passed on `batch/step.py`.
  for (const filename of layerFiles(modelsDir).sort()) {
    const source = readFileSync(join(modelsDir, filename), "utf-8");
    for (const model of splitModels(source)) {
      if (/__tablename__/.test(model.body)) {
        issues.push(...checkModel(filename, model.name, model.bases, model.body));
        continue;
      }
      // A mixin owns no table, but its columns land in every table that
      // inherits it — so the column-level invariants still apply. Skipping
      // mixins let AuditMixin drift (an unbounded created_by, a naive
      // timestamp) past every check.
      if (/mapped_column\(/.test(model.body)) {
        issues.push(...checkColumns(`${filename}:${model.name}`, model.name, model.body));
      }
    }
  }
  issues.push(...checkAuditMixin(readFileSync(join(modelsDir, "base.py"), "utf-8")));
  return issues;
}

/**
 * `AuditMixin` is the single place every table gets its audit trail and its
 * optimistic-lock counter from. Losing a column here silently disarms the
 * invariant for every table at once.
 */
function checkAuditMixin(source: string): string[] {
  const issues: string[] = [];
  const mixin = splitModels(source).find((model) => model.name === "AuditMixin");
  if (mixin === undefined) return ["base.py: AuditMixin is required"];
  for (const column of ["created_by", "updated_by", "created_at", "updated_at", "version"]) {
    if (!new RegExp(`^\\s{4}${column}:`, "m").test(mixin.body)) {
      issues.push(`base.py:AuditMixin: ${column} column is required`);
    }
  }
  // Optimistic locking is only real when the mapper is told to use the counter.
  if (!/version_id_col/.test(mixin.body)) {
    issues.push(
      'base.py:AuditMixin: __mapper_args__ must set version_id_col — without it the ' +
        "version column is decoration and concurrent writes silently overwrite",
    );
  }
  return issues;
}

/**
 * Splits a module into class blocks with their bodies. Base-less declarations
 * (`class AuditMixin:`) count: mixins carry columns that land in every table.
 */
function splitModels(source: string): Array<{ name: string; bases: string; body: string }> {
  const models: Array<{ name: string; bases: string; body: string }> = [];
  const re = /^class\s+(\w+)(?:\(([^)]*)\))?:$/gm;
  const starts: Array<{ name: string; bases: string; index: number }> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) {
    starts.push({ name: m[1], bases: m[2] ?? "", index: m.index });
  }
  for (let i = 0; i < starts.length; i++) {
    const end = i + 1 < starts.length ? starts[i + 1].index : source.length;
    models.push({
      name: starts[i].name,
      bases: starts[i].bases,
      body: source.slice(starts[i].index, end),
    });
  }
  return models;
}

/** Parses `name: Mapped[type] = mapped_column(args)` declarations from a body. */
function parseColumns(body: string): Column[] {
  const columns: Column[] = [];
  const re = /^\s{4}(\w+):\s*Mapped\[([^\]]+)\]\s*=\s*mapped_column\(([\s\S]*?)\)\s*$/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(body)) !== null) {
    columns.push({ name: m[1], type: m[2].trim(), args: m[3] });
  }
  return columns;
}

function checkModel(file: string, name: string, bases: string, body: string): string[] {
  const issues: string[] = [];
  const where = `${file}:${name}`;

  // --- 1. __tablename__ present, lower snake case, singular ---
  const tableMatch = body.match(/__tablename__\s*=\s*"([^"]+)"/);
  if (tableMatch === null) {
    issues.push(`${where}: __tablename__ is required`);
  } else {
    const table = tableMatch[1];
    if (!/^[a-z][a-z0-9_]*$/.test(table)) {
      issues.push(`${where}: __tablename__ "${table}" must be lower snake case`);
    }
    if (/[^s]s$/.test(table)) {
      issues.push(`${where}: __tablename__ "${table}" must be singular`);
    }
  }

  // --- 2. Primary key declared ---
  if (!/primary_key=True/.test(body)) {
    issues.push(`${where}: a primary key is required`);
  }

  // --- 3. AuditMixin inherited ---
  if (!/\bAuditMixin\b/.test(bases)) {
    issues.push(`${where}: table models must inherit AuditMixin (created_by/updated_by/created_at/updated_at)`);
  }

  issues.push(...checkColumns(where, name, body));
  return issues;
}

/** Column-level invariants — shared by table models and column-bearing mixins. */
function checkColumns(where: string, _name: string, body: string): string[] {
  const issues: string[] = [];
  const columns = parseColumns(body);

  // --- 4. Atomicity (1NF) — no numbered repeating groups ---
  const stems = new Map<string, string[]>();
  for (const column of columns) {
    const numbered = column.name.match(/^(.*?)_?(\d+)$/);
    if (numbered === null) continue;
    const stem = numbered[1];
    const group = stems.get(stem) ?? [];
    group.push(column.name);
    stems.set(stem, group);
  }
  for (const [stem, group] of stems) {
    if (group.length >= 2) {
      issues.push(
        `${where}: numbered columns ${group.join(", ")} are a repeating group — ` +
          `model "${stem}" repetition as rows in a child table (1NF)`,
      );
    }
  }

  for (const column of columns) {
    const at = `${where}.${column.name}`;

    // --- 5. Booleans not nullable ---
    if (column.type === "bool | None") {
      issues.push(`${at}: Boolean must be NOT NULL — three-state logic; give it a default`);
    }

    // --- 6. Timezone-aware timestamps ---
    if (/\bDateTime\(/.test(column.args) && !/timezone=True/.test(column.args)) {
      issues.push(`${at}: DateTime must use timezone=True`);
    }

    // --- 7. Foreign key contract ---
    if (/\bForeignKey\(/.test(column.args)) {
      if (!column.name.endsWith("_id")) {
        issues.push(`${at}: foreign key column must be named <referenced_table>_id`);
      }
      if (!/ondelete=/.test(column.args)) {
        issues.push(`${at}: ForeignKey must declare ondelete= explicitly`);
      }
      if (!/index=True/.test(column.args)) {
        issues.push(`${at}: foreign key column must carry index=True`);
      }
    }

    // --- 8. String columns declare an explicit length ---
    // A bare String is an unbounded varchar: no input contract at the DB layer,
    // and no signal about what the column is meant to hold.
    if (
      column.type.startsWith("str") &&
      !/String\(/.test(column.args) &&
      !/\b(Uuid|Text|JSON|Enum)\b/.test(column.args)
    ) {
      issues.push(`${at}: String column must declare an explicit length, e.g. String(120)`);
    }

    // --- 9. Closed value sets carry a check constraint ---
    if (!CLOSED_SET_SUFFIX.test(column.name)) continue;
    const length = column.args.match(/String\((\d+)\)/);
    if (length === null || Number(length[1]) > CLOSED_SET_MAX_LENGTH) continue;
    if (!new RegExp(`${column.name} IN \\(`).test(body)) {
      issues.push(
        `${at}: closed value set needs a CheckConstraint "${column.name} IN (...)" — ` +
          "an unconstrained column accepts any string",
      );
    }
  }

  return issues;
}

// Direct execution (make check-backend-table-design): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-table-design.ts")) {
  const issues = checkBackendTableDesignSync();
  console.log("==> check-backend-table-design");
  if (issues.length === 0) {
    console.log("    PASS: backend table design invariants valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-table-design");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
