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
import {
  listIntegrationCallerInputs,
  listIntegrationOperationCodes,
  listIntegrationProviderCodes,
  listIntegrationResponseKeys,
} from "../lib/backend-migration-policy.ts";

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

    // 7. A job that fills a ledger says which ledger, in its own name.
    issues.push(...checkJobNamesItsLedger(f, content));

    // 8. Every knob is a named constant the caller can override.
    issues.push(...checkJobKnobs(f, content, moduleJobs(content)));

    // 9. A job that walks an external feed states its incremental settings.
    issues.push(...checkSyncJobSettings(f, content));

    // 10. And the configuration it names exists in a migrated database.
    issues.push(...checkSeededConfiguration(f, content));

    // 11. And the ledger it fills reads every key that configuration answers.
    issues.push(...checkLedgerReadsTheContract(content));

    // 12. And it walks positions - a filter would migrate a subset.
    issues.push(...checkMigrationWalksPositions(f, content));
  }

  issues.push(...checkDatabaseManagedSchedule(batchDir));
  issues.push(...checkResumeVocabularyExists());

  return issues;
}

/**
 * The names `checkResumeContract` greps for must still exist in the code it
 * guards, or the guard is a regex matching nothing.
 *
 * Measured: renaming `next_range_start` to `resume_position` left this check
 * green while it recognised no job as consuming a cursor - every invariant it
 * enforces had silently switched off, and only a planted violation showed it.
 * A string-based check cannot survive a rename; it can at least refuse to run
 * blind.
 */
function checkResumeVocabularyExists(): string[] {
  const issues: string[] = [];
  const model = join(projectRoot, "backend", "app", "models", "batch", "checkpoint.py");
  const service = join(projectRoot, "backend", "app", "services", "batch", "checkpoint.py");
  const wanted: [string, string, RegExp][] = [
    [model, "resume_position", /^\s+resume_position\s*:/m],
    [model, "resume_key", /^\s+resume_key\s*:/m],
    [service, "find_checkpoint", /def find_checkpoint\(/],
    [service, "update_resume_point", /def update_resume_point\(/],
  ];
  for (const [path, name, pattern] of wanted) {
    if (existsSync(path) && pattern.test(readFileSync(path, "utf-8"))) continue;
    issues.push(
      `check-backend-batch: the resume-contract check looks for \`${name}\` and ` +
        `${path.replace(projectRoot + "/", "")} no longer declares it - the check is ` +
        "blind until its vocabulary follows the rename",
    );
  }
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
 * A job that writes a domain's ledger carries that domain in its name.
 *
 * The naming chain this file already enforces — module = function = registry key
 * = seeded `batch_schedule.code` — is self-consistent by construction, so it
 * stayed green while the thing the job *writes* was renamed underneath it:
 * `barcode` became `food_barcode` and `sync_barcode_ledger` kept a noun that no
 * longer named a table. Five equal names, all of them stale together.
 *
 * The domain is read from the job's own imports, and no name is listed here: a
 * job reaches its subject through a **flat** `from app.services.<domain> import`,
 * while the services every job uses to record itself arrive dotted
 * (`app.services.batch.run`, `app.services.integration.operation`) and never
 * match. The batch layer is forbidden from touching repositories or the session
 * directly (checks 2 and 3 above), so that flat import is the job's subject.
 */
function checkJobNamesItsLedger(file: string, content: string): string[] {
  const domains = [...content.matchAll(/from app\.services\.(\w+) import/g)].map(
    (match: RegExpMatchArray) => match[1],
  );
  if (domains.length !== 1) return [];

  const [domain] = domains;
  const job = file.replace(/\.py$/, "");
  if (job.includes(domain)) return [];
  return [
    `app/batch/${file}: writes the ${domain} ledger but is called '${job}' — the job's name ` +
      "carries the domain it fills, or a renamed table leaves the schedule, the module and " +
      "the seeded code all naming something that no longer exists",
  ];
}

/**
 * A knob is a named constant, and the job takes it as a parameter.
 *
 * Both archetypes in this layer run on numbers that were *measured*: the sync
 * job's window (1000 rows — 1001 rides a provider bug) and its ceiling (100
 * pages against a 53,242-row feed), the purge job's retention (90 days). A
 * number written into the call instead is a measurement with nowhere to record
 * what it measured, and it cannot be narrowed for one run: an operator
 * re-syncing a single window has to edit the module.
 *
 * So: every parameter of the job defaults to an `UPPER_SNAKE` module constant,
 * and every `DEFAULT_*` constant is some parameter's default. The second half
 * matters as much as the first — an orphan `DEFAULT_PAGE_SIZE` is a knob the
 * job reads directly, which reads like a setting and behaves like a literal.
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
 * A job that walks an external feed states its incremental settings.
 *
 * The two archetypes in this layer differ in what they are incremental *by*:
 *
 * - **Sync** (`sync_food_barcode_ledger`) fills a ledger from a provider. Its
 *   increment is a position in the feed — a window of rows, a ceiling on how
 *   many windows one pass may take, and a cursor that survives the run. All
 *   three are settings, and the provider is named by configuration codes rather
 *   than by a URL, because the path, the key and the paging family live in
 *   `integration_field`.
 * - **Maintenance** (`purge_old_batch_runs`) has no feed and no cursor. Its
 *   increment is time: a retention constant and a cutoff computed from the
 *   clock. `checkResumeContract` already refuses it a cursor it does not need.
 *
 * A sync job that omits the ceiling is the failure this states: a provider that
 * ignores a filter answers 200 with a full unfiltered page forever, and a walk
 * with no bound follows it until the process dies.
 */
function checkSyncJobSettings(file: string, content: string): string[] {
  if (!/\.execute_operation\(/.test(content)) return [];
  const issues: string[] = [];

  for (const required of ["PROVIDER_CODE", "OPERATION_CODE"]) {
    if (new RegExp(`^${required}\\s*=`, "m").test(content)) continue;
    issues.push(
      `app/batch/${file}: no ${required} — a sync job names the configuration it runs, and ` +
        "the path, the key and the paging family live in integration_field, not here",
    );
  }
  if (!/^DEFAULT_\w*PAGE_SIZE\w*\s*=/m.test(content)) {
    issues.push(
      `app/batch/${file}: no DEFAULT_*PAGE_SIZE — the window a pass asks for is the ` +
        "measurement this job runs on, and a provider caps how wide it may be",
    );
  }
  if (!/^DEFAULT_MAX_\w+\s*=/m.test(content)) {
    issues.push(
      `app/batch/${file}: no DEFAULT_MAX_* ceiling — a provider that ignores a filter ` +
        "answers a full page forever, and an unbounded walk follows it until the process dies",
    );
  }
  issues.push(...checkPageFamilyCeiling(file, content));
  return issues;
}

/**
 * A PAGE-family job refuses a window wider than its provider's ceiling.
 *
 * Measured on `search-food-nutrition` (2026-09-05): `num_of_rows` of 501 and
 * up answers HTTP 200 with an empty list - the shape of the end of the feed.
 * A job configured past the ceiling imports nothing, stops on its "short" first
 * page and reports success every night, and no other gate sees it: the call
 * succeeded. The family is read off the operation's seeded caller inputs, so a
 * job is asked for the guard exactly when its feed pages by number.
 */
function checkPageFamilyCeiling(file: string, content: string): string[] {
  const operation = /^OPERATION_CODE\s*=\s*"([^"]+)"/m.exec(content)?.[1];
  if (operation === undefined) return [];
  const inputs = listIntegrationCallerInputs().get(operation) ?? [];
  if (!inputs.includes("num_of_rows")) return [];
  const issues: string[] = [];
  if (!/^MAX_PAGE_SIZE\s*=/m.test(content)) {
    issues.push(
      `app/batch/${file}: pages by number (${operation} takes num_of_rows) but declares no ` +
        "MAX_PAGE_SIZE - past the provider's ceiling a window answers 200 with no rows, " +
        "which reads as the end of the feed",
    );
  } else if (!/page_size\s*>\s*MAX_PAGE_SIZE/.test(content)) {
    issues.push(
      `app/batch/${file}: declares MAX_PAGE_SIZE but never refuses a page_size above it - ` +
        "a caller asking for more believes it will get more, and gets an empty page instead",
    );
  }
  return issues;
}

/**
 * The provider and operation a sync job names must be rows a revision inserts.
 *
 * `PROVIDER_CODE` and `OPERATION_CODE` are strings resolved at 03:00 against
 * `integration_provider` / `integration_operation`. Nothing else in the stack
 * connects them: the job type-checks, its tests script the seam and never look
 * the codes up, and every gate stays green - measured, by pointing this job at
 * `search-ghost-material` and running the whole suite. The failure surfaces once
 * a night, in a scheduler log, as configuration that does not exist.
 *
 * Read from the migrations rather than the database, so a fresh clone answers
 * the same as the machine that already ran `migrate`.
 */
function checkSeededConfiguration(file: string, content: string): string[] {
  if (!/\.execute_operation\(/.test(content)) return [];
  const issues: string[] = [];
  const seeded: [string, () => string[], string][] = [
    ["OPERATION_CODE", listIntegrationOperationCodes, "integration_operation"],
    ["PROVIDER_CODE", listIntegrationProviderCodes, "integration_provider"],
  ];
  for (const [constant, codes, table] of seeded) {
    const declared = new RegExp(`^${constant}\\s*=\\s*"([^"]+)"`, "m").exec(content)?.[1];
    if (declared === undefined) continue;
    const known = codes();
    if (known.includes(declared)) continue;
    issues.push(
      `app/batch/${file}: ${constant} '${declared}' is seeded by no migration - ` +
        `a job whose ${table} row does not exist runs once a night and fails on ` +
        `configuration, not on data (seeded: ${known.join(", ") || "none"})`,
    );
  }
  return issues;
}

/**
 * A ledger's `from_record` and the operation's seeded record keys agree, both ways.
 *
 * The mapping is a list of `record.get("<key>")` calls, and nothing types it:
 * `record` is a `Mapping[str, object]`, so a misspelt key reads `None`, the
 * column is stored NULL on every record forever, and the run reports success.
 * The reverse drift is quieter still - a key added to the seed that the ledger
 * never reads is simply data the sync drops.
 *
 * A key the ledger declines on purpose (`row_no`, the record's position inside
 * its page) is declared in an `UNSTORED_KEYS` set beside `from_record`, with
 * the reason, so the decline is a decision the check can read rather than an
 * omission it cannot tell from a mistake.
 */
function checkLedgerReadsTheContract(content: string): string[] {
  const operation = /^OPERATION_CODE\s*=\s*"([^"]+)"/m.exec(content)?.[1];
  if (operation === undefined) return [];
  const seeded = listIntegrationResponseKeys().get(operation);
  if (seeded === undefined || seeded.length === 0) return [];
  // The ledger is the one service the job imports from outside the batch and
  // integration layers: `app.services.<domain>.<table>` has its schema at
  // `app/schemas/<domain>/<table>.py`. The batch layer's own services (run,
  // step, checkpoint) and the integration seam are imported by every sync job.
  // Every sync job imports its run/step/checkpoint services and the provider
  // seam by construction; those are the job's plumbing, and the ledger it fills
  // is whichever service is left.
  const service = [...content.matchAll(/^from app\.services\.([a-z_]+)\.([a-z_]+) import \w+Service$/gm)]
    // domain-literal: batch and integration are the plumbing layers, never the ledger
    .find((m) => m[1] !== "batch" && m[1] !== "integration");
  if (service === undefined) return [];
  const schemaPath = join(projectRoot, "backend", "app", "schemas", service[1], `${service[2]}.py`);
  if (!existsSync(schemaPath)) return [];
  const schema = readFileSync(schemaPath, "utf-8");
  const label = `app/schemas/${service[1]}/${service[2]}.py`;
  const issues: string[] = [];

  const read = new Set([...schema.matchAll(/record\.get\("([a-z0-9_]+)"\)/g)].map((m) => m[1]));
  const unstored = new Set(
    [...(/^UNSTORED_KEYS\s*=\s*frozenset\(\{([^}]*)\}\)/m.exec(schema)?.[1] ?? "").matchAll(/"([a-z0-9_]+)"/g)]
      .map((m) => m[1]),
  );
  for (const key of read) {
    if (seeded.includes(key)) continue;
    issues.push(
      `${label}: from_record reads "${key}", which ${operation} never answers - the column ` +
        "is NULL on every record and the sync reports success",
    );
  }
  for (const key of seeded) {
    if (read.has(key) || unstored.has(key)) continue;
    issues.push(
      `${label}: ${operation} answers "${key}" and the ledger neither stores it nor declines ` +
        "it in UNSTORED_KEYS - data dropped on the floor, or a column that was never added",
    );
  }
  return issues;
}

/**
 * A migration walks positions; it never sends a filter.
 *
 * Every operation here seeds optional caller inputs beside its paging keys -
 * `change_date`, `changed_from`, `last_updated_from`, `update_date`, a product
 * name, a licence number. Each reads a *subset*, and a subset is not a
 * migration: a job that sent `change_date` would import what changed since a
 * date and call the ledger complete. The temptation is real - measured on
 * `search-food-item-report`, the unfiltered walk is capped at 100 calls an hour
 * (`INFO-320`) and the date filter is not - and the answer is to pay the quota
 * in runs, which the checkpoint exists for.
 *
 * So the window a sync job sends holds the paging family's keys and nothing the
 * seed lists as a caller input. Read as dict-key syntax (`"key":`), because the
 * job's docstring names the filters it refuses.
 */
function checkMigrationWalksPositions(file: string, content: string): string[] {
  const operation = /^OPERATION_CODE\s*=\s*"([^"]+)"/m.exec(content)?.[1];
  if (operation === undefined) return [];
  const paging = new Set(["range_start", "range_end", "page_no", "num_of_rows"]);
  const issues: string[] = [];
  for (const key of listIntegrationCallerInputs().get(operation) ?? []) {
    if (paging.has(key)) continue;
    if (!new RegExp(`"${key}"\\s*:`).test(content)) continue;
    issues.push(
      `app/batch/${file}: sends "${key}" to ${operation} - a filter reads a subset, and a ` +
        "migration is everything; the increment is the checkpoint's position, never a date",
    );
  }
  return issues;
}

/**
 * Half a resume contract is worse than none, and every half passes every other
 * gate, because each is a working call.
 *
 * The checkpoint is the batch layer's common place, and NULL there is a fact
 * of its own — "this source has no row cursor" (migration 89, `find_checkpoint`
 * docstring). So reading a checkpoint proves nothing about paging: a cutoff job
 * may read its row, find no cursor, and recompute from the clock. What proves a
 * row cursor is what a job *does* with the row: it consumes `resume_position`,
 * or it calls `update_resume_point`, whose signature takes an `int` and cannot
 * write anything else.
 *
 * - A job that consumes `resume_position` and never advances it walks the
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
  const consumesCursor = reads && /\.resume_position\b/.test(content);
  const advances = /\.update_resume_point\(/.test(content);
  const readsRun = /\bcurrent_run_id\.get\(\)/.test(content);
  const recordsStep = /\.create_finished_step\(/.test(content);
  // A provider called from inside a loop is a paged feed — one call per window.
  const pagesFeed = /\.execute_operation\(/.test(content) && /^\s*(for|while)\b/m.test(content);

  if (consumesCursor && !advances) {
    issues.push(
      `${file}: consumes its cursor (checkpoint.resume_position) but never advances it ` +
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
 * The job codes some migration writes into `batch`.
 *
 * Discovered from the revisions themselves — never a hardcoded list — so a new
 * seed is found the moment it is written, and a deleted one stops counting.
 */
/**
 * The codes a migrated database actually carries — inserts, minus renames.
 *
 * `seededBatchCodes` is deliberately crude (every string literal in a revision
 * that touches the table) because it answers "is this code seeded *somewhere*",
 * and a superset is safe for that. The reverse question — "does every scheduled
 * row have a module?" — needs the exact set, or `"code"` and `"name"` would be
 * reported as jobs nobody wrote.
 *
 * So this reader resolves what the revisions do: a `bulk_insert` adds the code
 * it carries (through a `JOB_CODE = "..."` constant, which is how revision 82
 * writes it), and an update that renames one code to another removes the old and
 * adds the new. Revision 82 seeds `sync_barcode_ledger`; revision 92 renames it;
 * the answer is one code, the one a database has after `upgrade head`.
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
    const resolve = (token: string): string | null => {
      const literal = /^"([^"]+)"$/.exec(token.trim());
      if (literal !== null) return literal[1];
      return constants.get(token.trim()) ?? null;
    };

    for (const match of content.matchAll(/"code":\s*([^,\n}]+)/g)) {
      const code = resolve(match[1]);
      if (code !== null) codes.add(code);
    }
    for (const match of content.matchAll(/\.c\.code\s*==\s*([^)\n]+)\)/g)) {
      const code = resolve(match[1]);
      if (code !== null) codes.delete(code);
    }
    for (const match of content.matchAll(/\bcode=([^,\n)]+)/g)) {
      const code = resolve(match[1]);
      if (code !== null) codes.add(code);
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
