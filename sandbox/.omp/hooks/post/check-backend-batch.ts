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
 *   6. A job that consumes a row cursor advances it, a paged feed asks its
 *      checkpoint, and a paging job records steps under the run in context —
 *      half a resume contract passes every other gate and resumes nothing.
 *      A checkpoint with a NULL cursor is a fact, not a violation
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
  const astRulesDir = join(projectRoot, ".omp", "ast-grep", "rules", "batch");
  if (existsSync(astRulesDir)) {
    issues.push(...runAstRules(astRulesDir, [batchDir]));
  }

  for (const f of readdirSync(batchDir)) {
    if (!f.endsWith(".py") || f === "__init__.py") continue;

    const content = readFileSync(join(batchDir, f), "utf-8");

    // 1. Must use engine directly from app.core.database
    if (!/from app\.core\.database import\s+.*\bengine\b/.test(content)) {
      issues.push(`${f}: must use engine directly (from app.core.database import engine)`);
    }

    // 2. Must construct a service with Service(session) — never receive session from DI
    if (!/\b\w+Service\(session\)/.test(content)) {
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

    // 4. Must return a meaningful count/status
    if (!/return\s+\w*(?:count|deleted|total|status)\w*/.test(content)) {
      issues.push(`${f}: must return a meaningful count/status (e.g. return deleted)`);
    }

    // 5. The job itself is async — checked on the declaration, not on the file.
    // `content.includes("async def")` passed a sync job the moment the module
    // held one async helper, which is the shape a job file always has.
    issues.push(...checkJobFileName(f, moduleJobs(content)));

    // 6. A cursor is read and advanced by the same job; a step belongs to a run.
    issues.push(...checkResumeContract(f, content));
  }

  issues.push(...checkDatabaseManagedSchedule(batchDir));

  return issues;
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
 * Half a resume contract is worse than none, and every half passes every other
 * gate, because each is a working call.
 *
 * The checkpoint is the batch layer's common place, and NULL there is a fact
 * of its own — "this source has no row cursor" (migration 89, `find_checkpoint`
 * docstring). So reading a checkpoint proves nothing about paging: a cutoff job
 * may read its row, find no cursor, and recompute from the clock. What proves a
 * row cursor is what a job *does* with the row: it consumes `next_range_start`,
 * or it calls `update_resume_point`, whose signature takes an `int` and cannot
 * write anything else.
 *
 * - A job that consumes `next_range_start` and never advances it walks the
 *   whole feed every night from the same cursor — the 54 calls the tail was
 *   kept to avoid — while its row says it resumed.
 * - A job that advances a cursor it never read starts at row 1 every run and
 *   stores a position nothing consults.
 * - A job that calls a provider from inside a loop pages a feed, and a paged
 *   feed decides what its checkpoint means by reading it — a NULL row, a
 *   cursor, or no row at all; a walk that never asks decided nothing, and
 *   restarts at row 1 without saying so.
 * - A paging job records one step per window: a run without steps has one
 *   fact, its ending — which window failed, how many rows a page carried,
 *   which provider call answered, all unrecoverable.
 * - A step needs the run in context (`current_run_id`): a job that writes steps
 *   without reading it either invents a run or attaches to none.
 *
 * Measured on call names, not on job names: any module in `app/batch/` that
 * touches one side of a pair owes the other. A job that never pages and never
 * touches a cursor owes nothing here — the purge jobs are that shape.
 */
function checkResumeContract(file: string, content: string): string[] {
  const issues: string[] = [];
  const reads = /\.find_checkpoint\(/.test(content);
  const consumesCursor = reads && /\.next_range_start\b/.test(content);
  const advances = /\.update_resume_point\(/.test(content);
  const readsRun = /\bcurrent_run_id\.get\(\)/.test(content);
  const recordsStep = /\.create_finished_step\(/.test(content);
  // A provider called from inside a loop is a paged feed — one call per window.
  const pagesFeed = /\.execute_operation\(/.test(content) && /^\s*(for|while)\b/m.test(content);

  if (consumesCursor && !advances) {
    issues.push(
      `${file}: consumes its cursor (checkpoint.next_range_start) but never advances it ` +
        "(update_resume_point) — every run walks the feed from the same position",
    );
  }
  if (advances && !reads) {
    issues.push(
      `${file}: advances a cursor it never reads (find_checkpoint) — the position is ` +
        "stored and nothing resumes from it",
    );
  }
  if (pagesFeed && !reads) {
    issues.push(
      `${file}: walks a provider feed page by page without asking its checkpoint ` +
        "(find_checkpoint) — a paged feed decides what its row means by reading it: " +
        "a cursor to resume from, NULL for no row cursor, or no row yet",
    );
  }
  if ((pagesFeed || advances) && !recordsStep) {
    issues.push(
      `${file}: pages a feed but records no step (BatchStepService.create_finished_step) ` +
        "— a failed run says which job, never which window",
    );
  }
  if (recordsStep && !readsRun) {
    issues.push(
      `${file}: records steps without reading the run in context (current_run_id.get()) ` +
        "— a step belongs to the run the scheduler opened, and a job run by hand has none",
    );
  }
  if (readsRun && !recordsStep) {
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
  for (const entry of registry[1].matchAll(/"([a-z0-9_]+)"\s*:\s*(\w+)/g)) {
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
 * The job codes some migration writes into `batch`.
 *
 * Discovered from the revisions themselves — never a hardcoded list — so a new
 * seed is found the moment it is written, and a deleted one stops counting.
 */
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
    if (!content.includes("bulk_insert")) continue;
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
