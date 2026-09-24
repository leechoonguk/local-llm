import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";

/**
 * Check-Backend-Batch Post Hook
 *
 * After tool execution, validates that batch jobs in backend/app/batch/
 * follow the conventions in .omp/rules/backend-batch.md:
 *   1. Use `engine` directly from app.core.database (never DI session)
 *   2. Use `<domain>_service = Service(session)` — domain-prefixed local var
 *   3. Never access the repository — call service methods instead
 *      (enforced globally by naming/repository-access.yml)
 *   4. Return a meaningful count/status
 *   5. No business logic — all work goes through service layer methods
 *   6. A job that walks a provider feed records one step per window under
 *      the run in context, and a job that reads the run writes steps under it
 *   7. Every knob is an UPPER_SNAKE constant and a parameter defaulted to it.
 *
 * What a provider job syncs and a derive job rebuilds — feeds, floors, the
 * ledger contract, derivations — is check-backend-ledger (backend-ledger.md).
 *
 * It also enforces that the *schedule* lives in the database, not in Python.
 * The chain a job must complete — function → registry → seeded row → scheduler
 * — is checked end to end, because every link that is missing fails silently:
 * an unregistered function is dead code, an unseeded code runs in no
 * environment, and a hand-written `add_job` in main.py is a schedule nobody can
 * change without a deploy (the exact regression this contract removed).
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
// Adjust cwd to project root if running from backend/
const projectRoot = resolveProjectRoot();

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */

export default function checkBackendBatch(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-batch", event, () => {
    // Skip read-only tools — they cannot change batch files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendBatchSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-batch"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-batch",
      issues,
      "run make check-backend-batch for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-batch") };
  }));
}

function checkBackendBatchSync(): string[] {
  const issues: string[] = [];
  const batchDir = join(projectRoot, "backend", "app", "batch");

  if (!existsSync(batchDir)) {
    issues.push("backend/app/batch/ directory not found");
    return issues;
  }

  // --- AST rule validation (ast-grep) ---
  // Structural checks that string matching cannot express precisely:
  //   batch/batch-job-async.yml           — batch job functions must be async def
  //   batch/batch-service-constructor.yml — must construct Service(session)
  // A ledger job opens no session and builds no service: it names its feed and
  // hands it to `sync_ledger`, which owns the pinned ledger session, the call
  // session and the steps for all of them. The
  // session rules still hold for every job that does its own work, so they run
  // over those files rather than over the directory.
  const astRulesDir = join(projectRoot, ".omp", "ast-grep", "rules", "batch");
  const ownWorkFiles = readdirSync(batchDir)
    .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
    .map((f: string) => join(batchDir, f))
    .filter((path: string) => !delegatesToLedgerRunner(readFileSync(path, "utf-8")));
  if (existsSync(astRulesDir) && ownWorkFiles.length > 0) {
    issues.push(...runAstRules(astRulesDir, ownWorkFiles));
  }

  for (const f of readdirSync(batchDir)) {
    if (!f.endsWith(".py") || f === "__init__.py") continue;

    const content = readFileSync(join(batchDir, f), "utf-8");
    const delegates = delegatesToLedgerRunner(content);

    // 1. Must use engine directly from app.core.database
    if (!delegates && !/from app\.core\.database import\s+.*\bengine\b/.test(content)) {
      issues.push(`${f}: must use engine directly (from app.core.database import engine)`);
    }

    // 2. Must construct a service with Service(session) — never receive session from DI
    if (!delegates && !/\b\w+Service\(session\)/.test(content)) {
      issues.push(`${f}: must construct a service via Service(session) constructor`);
    }

    // 3. Repository access is forbidden outside services — enforced globally
    //    by naming/repository-access.yml (check-backend-domain.ts scans
    //    services/repositories/routers/batch). Batch jobs call service
    //    methods instead (item_service.find_stale(...)).
    // Raw session usage (execute/get/add/commit/rollback/delete) is
    // forbidden — the session is only created via AsyncSession(engine) and
    // passed to the service. Read/write phases use separate sessions so the
    // read session's close() releases the autobegun read transaction.
    if (/session\.(execute|get|add|commit|rollback|delete)\b/.test(content)) {
      issues.push(`${f}: raw session usage forbidden — go through service.<domain>_repository / service methods`);
    }

    // 4. Must return a meaningful count/status. `written` is what a ledger
    //    job answers: the rows the night changed, over every feed.
    if (
      !/return\s+\w*(?:count|deleted|total|status|written)\w*/.test(content) &&
      !(delegates && /return await sync_ledger\(/.test(content))
    ) {
      issues.push(`${f}: must return a meaningful count/status (e.g. return deleted, return written)`);
    }

    // 5. The job itself is async — checked on the declaration, not on the file.
    // `content.includes("async def")` passed a sync job the moment the module
    // held one async helper, which is the shape a job file always has.
    issues.push(...checkJobFileName(f, moduleJobs(content)));

    // 6. A walked feed is recorded in steps; a step belongs to a run.
    issues.push(...checkRunContract(f, content));

    // 7. Every knob is a named constant the caller can override.
    issues.push(...checkJobKnobs(f, content, moduleJobs(content)));
  }

  // 8. The schedule is a table: registry, seeded row, scheduler options, lifespan.
  issues.push(...checkDatabaseManagedSchedule(batchDir));

  // What a provider job syncs and a derive job rebuilds is check-backend-ledger.
  issues.push(...checkCodesFitTheirColumns());

  return issues;
}

/**
 * A ledger job states its feed and hands the walk to the shared runner.
 *
 * `sync_ledger` (app/services/batch/ledger_feed.py) owns the pinned ledger
 * session, the call session, the step per window and the failure, so a ledger
 * job holds four constants and one call. The checks that read a job for its
 * own session and its own service are about jobs that do their own work.
 */
function delegatesToLedgerRunner(content: string): boolean {
  return /\bsync_ledger\(/.test(content);
}

/**
 * One job, one module, named after it: `app/batch/<job_code>.py`.
 *
 * The identity is a chain of equal names — module = function = `BATCH_JOBS` key
 * = the `batch_schedule.code` a seeded row carries. That is what makes the log
 * navigable in one step: a row that failed at 04:00 says `purge_old_batch_runs`,
 * and the file is `app/batch/purge_old_batch_runs.py`, its test
 * `tests/batch/test_purge_old_batch_runs.py`.
 *
 * The convention is the same one `check-backend-model-files` and
 * `check-backend-repository-files` already enforce — a file is named after the
 * one thing it owns — and `app/batch/` was the layer that had no rule.
 * Measured before it: the job purging batch runs lived in `runs.py`, one letter
 * from `models/batch/run.py`, so the file name said which *domain* the job read
 * rather than which job it was; three job files, three different naming ideas
 * (a plural domain, a plural table, a plural noun).
 *
 * A module with two public jobs is rejected rather than renamed: two jobs
 * cannot both be the file's name, and splitting them is the only outcome that
 * keeps the chain readable in either direction.
 */
function checkJobFileName(file: string, jobs: JobDeclaration[]): string[] {
  const moduleName = file.replace(/\.py$/, "");
  if (jobs.length === 0) {
    return [
      `app/batch/${file}: defines no job — a module here is one scheduled function, and a ` +
        "file that schedules nothing belongs beside the code that calls it",
    ];
  }
  if (jobs.length > 1) {
    const names = jobs.map((job) => job.name).join(", ");
    return [
      `app/batch/${file}: defines ${jobs.length} jobs (${names}) — one job per ` +
        "module, because the module is named after the job it holds",
    ];
  }
  const [job] = jobs;
  if (job.name !== moduleName) {
    return [
      `app/batch/${file}: defines '${job.name}' — the module is named after its job, so this ` +
        `file is app/batch/${job.name}.py (and its test tests/batch/test_${job.name}.py)`,
    ];
  }
  if (!job.isAsync) {
    return [
      `app/batch/${file}: '${job.name}' is sync — the scheduler awaits the job, and a sync ` +
        "one blocks the loop every other job shares",
    ];
  }
  return [];
}


/**
 * A knob is a named constant, and the job takes it as a parameter.
 *
 * The maintenance job runs on a number that was *measured* (a retention of 90
 * days), and a number written into the call instead is a measurement with
 * nowhere to record what it measured; it cannot be narrowed for one run
 * either, so an operator has to edit the module.
 *
 * So: every parameter of the job defaults to an `UPPER_SNAKE` module constant,
 * and every `DEFAULT_*` constant is some parameter's default. The second half
 * matters as much as the first — an orphan `DEFAULT_PAGE_SIZE` is a knob the
 * job reads directly, which reads like a setting and behaves like a literal.
 * A provider job takes no parameter at all: its `PAGE_SIZE` is the portal's
 * cap, a fact, not a knob (check-backend-ledger).
 */
function checkJobKnobs(file: string, content: string, jobs: JobDeclaration[]): string[] {
  if (jobs.length !== 1) return [];
  const [job] = jobs;
  const signature = new RegExp(`async def ${job.name}\\(([^)]*)\\)`, "s").exec(content);
  const issues: string[] = [];
  const defaults = new Set<string>();

  if (signature !== null) {
    for (const parameter of signature[1].split(",")) {
      const assigned = /^\s*(\w+)\s*:[^=]*=\s*(.+?)\s*$/s.exec(parameter);
      if (assigned === null) continue;
      const [, name, value] = assigned;
      if (/^[A-Z][A-Z0-9_]*$/.test(value)) {
        defaults.add(value);
        continue;
      }
      issues.push(
        `app/batch/${file}: '${name}' defaults to ${value} — a job's knobs are named module ` +
          "constants, so the number that was measured has somewhere to say what it measured",
      );
    }
  }

  for (const match of content.matchAll(/^(DEFAULT_[A-Z0-9_]+)\s*=/gm)) {
    if (defaults.has(match[1])) continue;
    issues.push(
      `app/batch/${file}: ${match[1]} is no parameter's default — a knob the job reads ` +
        "directly cannot be narrowed for one run, which is the only reason it is a constant",
    );
  }
  return issues;
}






/**
 * A walked feed leaves steps, and a step belongs to the run in context.
 *
 * - A job that walks a provider feed records one step per window: a run
 *   without steps has one fact, its ending — which window failed, how many
 *   rows a page carried, which provider call answered, all unrecoverable.
 * - A step needs the run in context (`current_run_id`): a job that writes steps
 *   without reading it either invents a run or attaches to none.
 * - And the reverse: a job that reads the run and writes nothing under it read
 *   it for no reason.
 *
 * Measured on call names, not on job names: any module in `app/batch/` that
 * touches one side of a pair owes the other. A job that never walks a feed
 * owes nothing here — the purge jobs are that shape.
 */
/**
 * Every job's signature fits the column that stores it.
 *
 * A job signs the rows it writes `batch:<job code>`, and that string lands in
 * `AuditMixin.created_by`/`updated_by`. Measured: three
 * jobs renamed after their ledgers were 51 to 57 characters
 * against a 50-wide column, and each one opened its run, wrote its first call
 * log, and died on `StringDataRightTruncationError` before the portal was ever
 * called - a night lost to a width nothing compared.
 *
 * The same reading covers the other code-shaped strings: a `batch_schedule.code`
 * and an `integration_operation.code` are stored in columns of their own width,
 * and a seed longer than the column is the same failure at 03:00.
 */
function checkCodesFitTheirColumns(): string[] {
  const issues: string[] = [];
  const appDir = join(projectRoot, "backend", "app");
  if (!existsSync(appDir)) return issues;
  const widths = new Map<string, number>();
  const base = join(appDir, "models", "base.py");
  if (existsSync(base)) {
    const actor = /ACTOR_LENGTH\s*=\s*(\d+)/.exec(readFileSync(base, "utf-8"));
    if (actor !== null) widths.set("actor", Number(actor[1]));
  }
  const schedule = join(appDir, "models", "batch", "schedule.py");
  if (existsSync(schedule)) {
    const code = /code:\s*Mapped\[str\][^\n]*String\((\d+)\)/.exec(readFileSync(schedule, "utf-8"));
    if (code !== null) widths.set("schedule", Number(code[1]));
  }
  const actorWidth = widths.get("actor");
  const scheduleWidth = widths.get("schedule");
  for (const code of listJobCodes()) {
    const signature = `batch:${code}`;
    if (actorWidth !== undefined && signature.length > actorWidth) {
      issues.push(
        `app/core/scheduler.py: job '${code}' signs its rows '${signature}' (${signature.length} ` +
          `characters) but AuditMixin.created_by holds ${actorWidth} - the run fails on its ` +
          "first written row, before the portal is called",
      );
    }
    if (scheduleWidth !== undefined && code.length > scheduleWidth) {
      issues.push(
        `app/core/scheduler.py: job code '${code}' is ${code.length} characters but ` +
          `batch_schedule.code holds ${scheduleWidth} - the row that schedules it cannot be seeded`,
      );
    }
  }
  return issues;
}

/** Every job code the registry names. */
function listJobCodes(): string[] {
  const scheduler = join(projectRoot, "backend", "app", "core", "scheduler.py");
  if (!existsSync(scheduler)) return [];
  const content = readFileSync(scheduler, "utf-8");
  const registry = /BATCH_JOBS[^{]*\{([\s\S]*?)\n\s*\}/.exec(content);
  if (registry === null) return [];
  return [...registry[1].matchAll(/"([a-z0-9_]+)"\s*:/g)].map((match) => match[1]);
}


function checkRunContract(file: string, content: string): string[] {
  const issues: string[] = [];
  const readsRun = /\bcurrent_run_id\.get\(\)/.test(content);
  const recordsStep = /\.create_finished_step\(/.test(content);
  const walksFeed = /\.walk_operation\(/.test(content);

  if (walksFeed && !recordsStep) {
    issues.push(
      `${file}: walks a feed but records no step (BatchStepService.create_finished_step) ` +
        "— a failed run says which job, never which window",
    );
  }
  if (recordsStep && !readsRun) {
    issues.push(
      `${file}: records steps without reading the run in context (current_run_id.get()) ` +
        "— a step belongs to the run the scheduler opened, and a job run by hand has none",
    );
  }
  // A job may also read the run to know which run is *itself* — the derive
  // job asks which other jobs are in flight, and its own row is in that answer.
  const excludesOwnRun = /excluding=current_run_id\.get\(\)/.test(content);
  if (readsRun && !recordsStep && !excludesOwnRun) {
    issues.push(
      `${file}: reads current_run_id but writes nothing under it — the run is read for ` +
        "steps, and a job that records none has no use for it",
    );
  }
  return issues;
}

interface JobDeclaration {
  name: string;
  isAsync: boolean;
}

/**
 * The module-level functions a `batch_schedule` row could name.
 *
 * `_` helpers are excluded: they cannot be scheduled, and requiring a registry
 * entry for one would push every helper out of the job file.
 */
function moduleJobs(content: string): JobDeclaration[] {
  const jobs: JobDeclaration[] = [];
  for (const match of content.matchAll(/^(async )?def (\w+)\(/gm)) {
    if (!match[2].startsWith("_")) jobs.push({ name: match[2], isAsync: match[1] !== undefined });
  }
  return jobs;
}

/**
 * The schedule is a table: every job is a registry entry and a seeded `batch`
 * row, and `main.py` schedules nothing by name.
 */
function checkDatabaseManagedSchedule(batchDir: string): string[] {
  const issues: string[] = [];
  const schedulerPath = join(projectRoot, "backend", "app", "core", "scheduler.py");
  if (!existsSync(schedulerPath)) {
    return ["backend/app/core/scheduler.py not found — the schedule has no owner"];
  }
  const scheduler = readFileSync(schedulerPath, "utf-8");

  // --- The registry: one place where a code becomes runnable Python ---
  const registry = /BATCH_JOBS[^=]*=\s*MappingProxyType\(\s*\{([\s\S]*?)\}\s*\)/.exec(scheduler);
  if (registry === null) {
    return ["core/scheduler.py: no `BATCH_JOBS = MappingProxyType({...})` registry found"];
  }
  const registered = new Map<string, string>();
    // The value may be parenthesised: a job code long enough to name its ledger
  // table wraps under the formatter, and the wrap is not a different entry.
  for (const entry of registry[1].matchAll(/"([a-z0-9_]+)"\s*:\s*\(?\s*(\w+)/g)) {
    registered.set(entry[1], entry[2]);
  }
  if (registered.size === 0) {
    issues.push("core/scheduler.py: BATCH_JOBS is empty — no code can be scheduled");
  }

  // --- Every job function is registered; every registered name exists ---
  const defined = new Set<string>();
  for (const file of readdirSync(batchDir)) {
    if (!file.endsWith(".py") || file === "__init__.py") continue;
    const content = readFileSync(join(batchDir, file), "utf-8");
    // A `_` helper is not a job: it cannot be scheduled, and demanding a
    // registry entry for it would push every module-level helper out of the
    // job file. The registry names what a `batch_schedule` row can call.
    for (const job of moduleJobs(content)) defined.add(job.name);
  }
  for (const name of defined) {
    if (![...registered.values()].includes(name)) {
      issues.push(
        `app/batch: '${name}' is in no BATCH_JOBS entry — a job no code names is dead code`,
      );
    }
  }
  for (const [code, name] of registered) {
    if (!defined.has(name) && !scheduler.includes(`import ${name}`)) {
      issues.push(`core/scheduler.py: BATCH_JOBS['${code}'] names '${name}', which no batch job defines`);
    }
    if (name !== code) {
      issues.push(
        `core/scheduler.py: BATCH_JOBS['${code}'] names '${name}' — the code a row carries is ` +
          "the function's own name, so a schedule in the database resolves to Python by " +
          "reading it, not by consulting this table",
      );
    }
  }

  // --- Every code is seeded: a job in no database runs in no environment ---
  const seeded = seededBatchCodes();
  // --- and the reverse: a row nothing runs is a schedule that fires nothing ---
  for (const code of scheduledBatchCodes()) {
    if (registered.has(code)) continue;
    issues.push(
      `'${code}' is scheduled by a migration but no module defines it — the scheduler skips ` +
        "such a row with a warning, so the job never runs and nothing on the screen says so",
    );
  }
  for (const code of registered.keys()) {
    if (!seeded.has(code)) {
      issues.push(
        `'${code}' is registered but no migration seeds a batch row for it — ` +
          "a job that exists only in Python never runs",
      );
    }
  }

  // --- main.py schedules nothing by name ---
  const mainPath = join(projectRoot, "backend", "app", "main.py");
  if (existsSync(mainPath)) {
    const main = readFileSync(mainPath, "utf-8");
    if (main.includes("add_job(")) {
      issues.push(
        "main.py: add_job() belongs to core/scheduler.py — a job scheduled in the " +
          "lifespan cannot be rescheduled or stopped without a deploy",
      );
    }
    if (!main.includes("list_enabled_batches")) {
      issues.push(
        "main.py: the lifespan must load the schedule from the database " +
          "(BatchService.list_enabled_batches)",
      );
    }
    // The sweep has no other caller: a killed process leaves its run RUNNING,
    // and only the next startup can say INTERRUPTED. main.py is excluded from
    // coverage, so deleting this call would pass every other gate silently.
    if (!main.includes("update_interrupted_runs")) {
      issues.push(
        "main.py: the lifespan must sweep orphaned runs " +
          "(BatchRunService.update_interrupted_runs) — a killed process cannot " +
          "close its own row, and nothing else survives it",
      );
    }
  }

  // --- The scheduler's own add_job carries the overlap policy ---
  // A reload without `id`/`replace_existing` stacks a second copy; without
  // `max_instances=1` two runs act on the same rows; without `coalesce` +
  // `misfire_grace_time` a restart across the scheduled minute skips the run
  // entirely, silently.
  for (const block of scheduler.split("add_job(").slice(1)) {
    const end = block.indexOf("\n        )");
    const call = end === -1 ? block : block.slice(0, end);
    for (const [option, why] of [
      ["id=", "a job with no id cannot be replaced or stopped"],
      ["replace_existing=True", "a reload otherwise stacks a second copy of the job"],
      ["max_instances=1", "two overlapping runs act on the same rows"],
      ["coalesce=True", "a backlog otherwise fires once per missed interval"],
      ["misfire_grace_time=", "a restart across the scheduled minute otherwise skips the run"],
    ]) {
      if (!call.includes(option)) {
        issues.push(`core/scheduler.py: add_job is missing \`${option}\` — ${why}`);
      }
    }
  }

  return issues;
}

/**
 * The codes a migrated database actually carries — inserts, minus renames and deletes.
 *
 * `seededBatchCodes` is deliberately crude (every string literal in a revision
 * that touches the table) because it answers "is this code seeded *somewhere*",
 * and a superset is safe for that. The reverse question — "does every scheduled
 * row have a module?" — needs the exact set, or `"code"` and `"name"` would be
 * reported as jobs nobody wrote.
 *
 * So this reader resolves what the revisions do, in order: a `bulk_insert` adds
 * the codes it carries — through a `JOB_CODE = "..."` constant (revision 82) or
 * a module-level `JOBS = [{"code": "..."}, ...]` list (revision 110) — an update
 * that renames one code to another removes the old and adds the new, and a
 * delete over `.c.code == X` or `.c.code.in_([...])` removes what it names. A
 * list constant is resolved to its codes, so `_seed(PROVIDER_JOBS)` and
 * `in_([job["code"] for job in RETIRED_JOBS])` read as the codes they carry.
 * Measured before the list case: revision 110 retired five jobs through a list
 * and this reader kept reporting them as scheduled by a migration nobody wrote.
 */
function scheduledBatchCodes(): Set<string> {
  const codes = new Set<string>();
  const versions = join(projectRoot, "backend", "alembic", "versions");
  if (!existsSync(versions)) return codes;

  for (const file of readdirSync(versions).sort(byRevision)) {
    if (!file.endsWith(".py")) continue;
    const source = readFileSync(join(versions, file), "utf-8");
    if (!/table\(\s*\n?\s*"batch(?:_schedule)?"/.test(source)) continue;
    // `upgrade()` only: a downgrade states the reverse of every line above it, so
    // reading both cancels the rename out — measured, the renamed-away code came
    // back from the downgrade and was reported as a row nobody runs.
    const upgradeAt = source.indexOf("def upgrade(");
    const downgradeAt = source.indexOf("def downgrade(");
    const content = source.slice(
      upgradeAt === -1 ? 0 : upgradeAt,
      downgradeAt === -1 ? source.length : downgradeAt,
    );

    const constants = new Map<string, string>();
    for (const match of source.matchAll(/^([A-Z][A-Z0-9_]*)\s*=\s*"([^"]+)"/gm)) {
      constants.set(match[1], match[2]);
    }
    // A module-level list of row dicts: every `"code": "..."` between the
    // opening bracket and the matching close at column 0.
    const lists = new Map<string, string[]>();
    for (const match of source.matchAll(/^([A-Z][A-Z0-9_]*)\s*(?::[^=]*)?=\s*\[\n([\s\S]*?)\n\]/gm)) {
      lists.set(match[1], [...match[2].matchAll(/"code":\s*"([^"]+)"/g)].map((m) => m[1]));
    }
    const resolve = (token: string): string[] => {
      const literal = /^"([^"]+)"$/.exec(token.trim());
      if (literal !== null) return [literal[1]];
      const constant = constants.get(token.trim());
      if (constant !== undefined) return [constant];
      const list = [...token.matchAll(/\b([A-Z][A-Z0-9_]*)\b/g)]
        .map((m) => lists.get(m[1]))
        .find((found) => found !== undefined);
      return list ?? [];
    };

    for (const match of content.matchAll(/"code":\s*([^,\n}]+)/g)) {
      for (const code of resolve(match[1])) codes.add(code);
    }
    for (const match of content.matchAll(/bulk_insert\([^,]+,\s*([^)\n]+)\)/g)) {
      for (const code of resolve(match[1])) codes.add(code);
    }
    for (const match of content.matchAll(/\.c\.code\s*==\s*([^)\n]+)\)/g)) {
      for (const code of resolve(match[1])) codes.delete(code);
    }
    for (const match of content.matchAll(/\.c\.code\.in_\(([^\n]+)\)\)/g)) {
      for (const code of resolve(match[1])) codes.delete(code);
    }
    for (const match of content.matchAll(/\bcode=([^,\n)]+)/g)) {
      for (const code of resolve(match[1])) codes.add(code);
    }
  }
  return codes;
}

/** Revisions apply in numeric order, and a rename only means anything in order. */
function byRevision(left: string, right: string): number {
  const number = (file: string) => Number.parseInt(file.split("_")[0], 10);
  return number(left) - number(right);
}

function seededBatchCodes(): Set<string> {
  const codes = new Set<string>();
  const versions = join(projectRoot, "backend", "alembic", "versions");
  if (!existsSync(versions)) return codes;
  for (const file of readdirSync(versions)) {
    if (!file.endsWith(".py")) continue;
    const content = readFileSync(join(versions, file), "utf-8");
    // Both names: revisions 80 and 82 seeded `batch`, and the table is
    // `batch_schedule` since revision 84. A reader that knew only the new name
    // would lose every historical seed; one that knew only the old name would
    // call the next job unseeded.
    // A code enters the schedule two ways, and only one of them is an insert:
    // revision 92 *renamed* a seeded job, and a reader that knew only
    // `bulk_insert` called the renamed job unseeded while the row was sitting in
    // every database. An update over the same table is the same fact — the code
    // this revision leaves behind is scheduled.
    const seeds = content.includes("bulk_insert");
    const renames = /\.update\(\)/.test(content);
    if (!seeds && !renames) continue;
    if (!/table\(\s*\n?\s*"batch(?:_schedule)?"/.test(content)) continue;
    for (const literal of content.matchAll(/"([a-z0-9_]+)"/g)) codes.add(literal[1]);
  }
  return codes;
}

// Direct execution (make check-backend-batch): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-batch.ts")) {
  const issues = checkBackendBatchSync();
  console.log("==> check-backend-batch");
  if (issues.length === 0) {
    console.log("    PASS: all batch jobs follow backend-batch.md conventions");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-batch");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
