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
  listIntegrationOperations,
  listIntegrationProviderCodes,
  listIntegrationResponseKeys,
} from "../lib/backend-migration-policy.ts";
import { feedsOf, listLedgerFeeds, type LedgerFeed } from "../lib/backend-ledger-feeds.ts";

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
 *   7. A provider job (`sync_<provider>_ledgers.py`) states one provider, one
 *      window, one end code set, and a `FEEDS` tuple that ties every operation
 *      it walks to the `replace_<table>_ledger` of that table's service — and
 *      every code it names is a row some migration seeded, of that provider.
 *   8. The reverse: every seeded operation that pages (`range_start` or
 *      `page_no` among its caller inputs) is a feed some provider job walks.
 *      An integration target is a ledger — seeding the operation is the first
 *      half of the work, and the table plus its `Feed` is the second.
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

    // 4. Must return a meaningful count/status. `written` is what a ledger
    //    job answers: the rows the night changed, over every feed.
    if (!/return\s+\w*(?:count|deleted|total|status|written)\w*/.test(content)) {
      issues.push(`${f}: must return a meaningful count/status (e.g. return deleted, return written)`);
    }

    // 5. The job itself is async — checked on the declaration, not on the file.
    // `content.includes("async def")` passed a sync job the moment the module
    // held one async helper, which is the shape a job file always has.
    issues.push(...checkJobFileName(f, moduleJobs(content)));

    // 6. A walked feed is recorded in steps; a step belongs to a run.
    issues.push(...checkRunContract(f, content));

    // 7. A provider job states its provider, its window and its feeds.
    const feeds = feedsOf(content, f.replace(/\.py$/, ""));
    issues.push(...checkProviderJobShape(f, content, feeds));

    // 8. Every knob is a named constant the caller can override.
    issues.push(...checkJobKnobs(f, content, moduleJobs(content)));

    // 9. And the configuration it names exists in a migrated database.
    issues.push(...checkSeededConfiguration(f, feeds));

    // 10. And every ledger it fills reads every key its feed answers.
    for (const feed of feeds) issues.push(...checkLedgerReadsTheContract(feed));

    // 11. And it walks positions - a filter would migrate a subset.
    issues.push(...checkMigrationWalksPositions(f, content, feeds));
  }

  issues.push(...checkDatabaseManagedSchedule(batchDir));

  // 12. And, across every job: each seeded paging operation is somebody's feed.
  issues.push(...checkEveryPagingOperationIsAFeed());

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
 * A provider job is `sync_<provider>_ledgers.py`, and it says what a provider job says.
 *
 * The shape is one rule for every feed: one `PROVIDER_CODE`, one `PAGE_SIZE`
 * (the portal's cap, measured), one `END_CODES` (what the portal answers past
 * its last row), one `SYNCED_BY`, and a `FEEDS` tuple of `Feed(<operation>,
 * <Service>, <Service>.replace_<table>_ledger)`. Nothing else is a setting:
 * there is no cursor, no ceiling on windows and no `total_count`, because the
 * feeds carry no change stamp to follow and the count lies on some operations
 * (measured 2026-09-06), so a pass is the whole feed every night.
 *
 * Each half of the shape is a fact somewhere else in the stack:
 *
 * - The name carries the provider's code, or its leading tokens
 *   (`mfds-food-safety-korea` → `sync_mfds_ledgers`), so a renamed provider
 *   leaves the schedule, the module and the seeded code naming nothing.
 *   Measured before it: five jobs named after tables, all stale together when
 *   `barcode` became `food_barcode`.
 * - The service a feed names is imported from `app.services.<domain>.<table>`,
 *   and the method it hands over is that table's `replace_<table>_ledger` -
 *   the only path through `LedgerStage`, whose floor refuses a pass that came
 *   back empty or lost half the ledger. A feed replaced any other way has no
 *   floor.
 * - Every walk is asked with the module's own window and end codes, so one
 *   feed cannot quietly page differently from its siblings.
 * - A feed fails alone: the job catches `LedgerFloorError` beside
 *   `IntegrationError` and raises after every feed had its turn.
 */
function checkProviderJobShape(file: string, content: string, feeds: LedgerFeed[]): string[] {
  const walks = /\.walk_operation\(/.test(content);
  const named = /^sync_[a-z0-9_]+_ledgers\.py$/.test(file);
  if (!walks && !named && feeds.length === 0) return [];
  const issues: string[] = [];
  const stem = file.replace(/\.py$/, "");

  if (!named) {
    issues.push(
      `app/batch/${file}: walks a provider feed but is not called sync_<provider>_ledgers.py - ` +
        "a job that replaces ledgers is named after the provider whose feeds it reads",
    );
  }
  for (const [required, why] of [
    ["PROVIDER_CODE", "the provider a job reads is a seeded code, never a URL"],
    ["PAGE_SIZE", "the window is the portal's measured cap, one for every feed"],
    ["END_CODES", "what the portal answers past its last row is one fact per portal"],
    ["SYNCED_BY", "the rows say which job wrote them"],
  ] as const) {
    if (new RegExp(`^${required}\\s*(?::[^=]*)?=`, "m").test(content)) continue;
    issues.push(`app/batch/${file}: no ${required} - ${why}`);
  }
  // Read off the code, not the prose: the docstring names what the job refuses.
  const code = content.replace(/"""[\s\S]*?"""/g, "").replace(/#[^\n]*/g, "");
  for (const retired of ["MAX_PAGE_SIZE", "DEFAULT_MAX_", "total_count", "find_checkpoint"]) {
    if (!code.includes(retired)) continue;
    issues.push(
      `app/batch/${file}: mentions ${retired} - a pass is the whole feed every night; the ` +
        "floor in LedgerStage is the only guard, and there is no cursor, ceiling or count",
    );
  }

  const provider = /^PROVIDER_CODE\s*=\s*"([^"]+)"/m.exec(content)?.[1];
  const token = /^sync_([a-z0-9_]+)_ledgers$/.exec(stem)?.[1].replace(/_/g, "-");
  if (provider !== undefined && token !== undefined && provider !== token && !provider.startsWith(`${token}-`)) {
    issues.push(
      `app/batch/${file}: reads '${provider}' but is called '${stem}' - the name is the ` +
        "provider's code or its leading tokens, so a renamed provider is found by name",
    );
  }

  if (feeds.length === 0) {
    issues.push(
      `app/batch/${file}: no FEEDS - a provider job is a tuple of ` +
        "Feed(<operation>, <Service>, <Service>.replace_<table>_ledger), one per ledger",
    );
  }
  for (const feed of feeds) {
    if (feed.table === "") {
      issues.push(
        `app/batch/${file}: ${feed.operation} names ${feed.service}, which is not imported from ` +
          "app.services.<domain>.<table> - the ledger a feed fills is a domain's table",
      );
      continue;
    }
    if (feed.replace !== `replace_${feed.table}_ledger`) {
      issues.push(
        `app/batch/${file}: ${feed.operation} replaces through ${feed.service}.${feed.replace}, ` +
          `but ${feed.service} is app/services/${feed.domain}/${feed.table}.py - the method is ` +
          `replace_${feed.table}_ledger, the one path through LedgerStage and its floor`,
      );
    }
  }

  for (const call of content.matchAll(/\.walk_operation\(([\s\S]*?)\n\s*\)/g)) {
    for (const [keyword, constant] of [["page_size", "PAGE_SIZE"], ["end_codes", "END_CODES"]]) {
      if (new RegExp(`${keyword}=${constant}\\b`).test(call[1])) continue;
      issues.push(
        `app/batch/${file}: a walk_operation call does not pass ${keyword}=${constant} - one ` +
          "window and one end code set for every feed of the provider, or one feed pages alone",
      );
    }
  }

  if (walks && !/except\s*\([^)]*\bLedgerFloorError\b[^)]*\)|except\s+LedgerFloorError\b/.test(content)) {
    issues.push(
      `app/batch/${file}: never catches LedgerFloorError - a feed under the floor is that ` +
        "feed's night, and the others still get their turn before the first failure is raised",
    );
  }
  return issues;
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
 * cap, a fact, not a knob (`checkProviderJobShape`).
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
 * The provider and every operation a job names must be rows a revision inserts,
 * and the operations must page the same way.
 *
 * `PROVIDER_CODE` and each feed's operation are strings resolved at 03:00
 * against `integration_provider` / `integration_operation`. Nothing else in the
 * stack connects them: the job type-checks, its tests script the seam and never
 * look the codes up, and every gate stays green - measured, by pointing a job at
 * `search-ghost-material` and running the whole suite. The failure surfaces once
 * a night, in a scheduler log, as configuration that does not exist.
 *
 * The family is a provider fact too: the job asks every feed for windows of
 * `PAGE_SIZE` and reads the end the same way, which only holds when the feeds
 * page by the same keys. A feed of the other family in the tuple would be
 * asked for `range_start` by a walk that sends `page_no`.
 *
 * Read from the migrations rather than the database, so a fresh clone answers
 * the same as the machine that already ran `migrate`.
 */
function checkSeededConfiguration(file: string, feeds: LedgerFeed[]): string[] {
  if (feeds.length === 0) return [];
  const issues: string[] = [];
  const providers = listIntegrationProviderCodes();
  const operations = listIntegrationOperationCodes();
  const inputs = listIntegrationCallerInputs();

  const [{ provider }] = feeds;
  if (provider !== "" && !providers.includes(provider)) {
    issues.push(
      `app/batch/${file}: PROVIDER_CODE '${provider}' is seeded by no migration - a job whose ` +
        "integration_provider row does not exist runs once a night and fails on " +
        `configuration, not on data (seeded: ${providers.join(", ") || "none"})`,
    );
  }
  const families = new Map<string, string>();
  const providerOf = new Map(listIntegrationOperations().map((op) => [op.code, op.provider]));
  for (const feed of feeds) {
    if (!operations.includes(feed.operation)) {
      issues.push(
        `app/batch/${file}: feed '${feed.operation}' is seeded by no migration - a job whose ` +
          "integration_operation row does not exist runs once a night and fails on " +
          `configuration, not on data (seeded: ${operations.join(", ") || "none"})`,
      );
      continue;
    }
    const owner = providerOf.get(feed.operation) ?? null;
    if (owner !== null && provider !== "" && owner !== provider) {
      issues.push(
        `app/batch/${file}: feed '${feed.operation}' is an operation of '${owner}', not of ` +
          `'${provider}' - the walk resolves (provider, operation) as a pair, and a job ` +
          "walks its own provider's feeds",
      );
    }
    const keys = inputs.get(feed.operation) ?? [];
    const family = keys.includes("range_start") ? "RANGE" : keys.includes("page_no") ? "PAGE" : "none";
    families.set(feed.operation, family);
  }
  const distinct = new Set(families.values());
  if (distinct.size > 1) {
    const listed = [...families].map(([operation, family]) => `${operation}=${family}`).join(", ");
    issues.push(
      `app/batch/${file}: its feeds page by different families (${listed}) - one provider job ` +
        "asks every feed for the same window, so a feed of another family belongs to another job",
    );
  }
  if (distinct.has("none")) {
    const unpaged = [...families].filter(([, family]) => family === "none").map(([op]) => op);
    issues.push(
      `app/batch/${file}: ${unpaged.join(", ")} seeds no paging keys (range_start or page_no) - ` +
        "a feed a walk cannot window is not a feed",
    );
  }
  return issues;
}

/**
 * Every seeded operation that pages is a feed of its provider's job.
 *
 * The forward checks read a job and ask whether what it names exists; this
 * one reads the seeds and asks whether what exists is walked. Without it, an
 * integration is "done" the moment its configuration is seeded and its
 * fixture recorded - and a paging operation nobody walks is a feed the
 * database never holds, which is the whole point of seeding one. Measured
 * on this tree: `search-product-classification` and `search-test-item` were
 * seeded (revision 64) and configured, and no job read either for the whole
 * life of the five-jobs design.
 *
 * Paging is the criterion, not existence: an operation without a window
 * (`range_start`/`page_no` absent from its caller inputs) is a lookup the API
 * answers per call, and a lookup has no feed to replace a ledger with.
 */
function checkEveryPagingOperationIsAFeed(): string[] {
  const issues: string[] = [];
  const backendApp = join(projectRoot, "backend", "app");
  const feeds = listLedgerFeeds(backendApp);
  const walked = new Set(feeds.map((feed) => feed.operation));
  const jobOf = new Map(feeds.map((feed) => [feed.provider, feed.job]));
  const inputs = listIntegrationCallerInputs();
  for (const operation of listIntegrationOperations()) {
    if (!operation.configured || walked.has(operation.code)) continue;
    const keys = inputs.get(operation.code) ?? [];
    if (!keys.includes("range_start") && !keys.includes("page_no")) continue;
    const provider = operation.provider ?? "its provider";
    const job = jobOf.get(provider) ?? `sync_${provider.replace(/-/g, "_")}_ledgers`;
    issues.push(
      `app/batch/${job}.py: seeded operation '${operation.code}' (${provider}) pages but no Feed ` +
        "walks it - an integration target is a ledger: build the table and its " +
        "`replace_<table>_ledger` (the `ledger` skill), then add " +
        `Feed("${operation.code}", <Table>Service, <Table>Service.replace_<table>_ledger) ` +
        `to FEEDS${jobOf.has(provider) ? "" : " of a new provider job"}`,
    );
  }
  return issues;
}

/**
 * A ledger's `from_record` and its feed's seeded record keys agree, both ways.
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
 *
 * Per feed: the schema is `app/schemas/<domain>/<table>.py`, the service's
 * sibling, and the keys are the ones the feed's operation answers.
 */
function checkLedgerReadsTheContract(feed: LedgerFeed): string[] {
  if (feed.table === "") return [];
  const seeded = listIntegrationResponseKeys().get(feed.operation);
  if (seeded === undefined || seeded.length === 0) return [];
  const schemaPath = join(projectRoot, "backend", "app", "schemas", feed.domain, `${feed.table}.py`);
  if (!existsSync(schemaPath)) return [];
  const schema = readFileSync(schemaPath, "utf-8");
  const label = `app/schemas/${feed.domain}/${feed.table}.py`;
  const issues: string[] = [];

  const read = new Set([...schema.matchAll(/record\.get\("([a-z0-9_]+)"\)/g)].map((m) => m[1]));
  const unstored = new Set(
    [...(/^UNSTORED_KEYS\s*=\s*frozenset\(\{([^}]*)\}\)/m.exec(schema)?.[1] ?? "").matchAll(/"([a-z0-9_]+)"/g)]
      .map((m) => m[1]),
  );
  for (const key of read) {
    if (seeded.includes(key)) continue;
    issues.push(
      `${label}: from_record reads "${key}", which ${feed.operation} never answers - the column ` +
        "is NULL on every record and the sync reports success",
    );
  }
  for (const key of seeded) {
    if (read.has(key) || unstored.has(key)) continue;
    issues.push(
      `${label}: ${feed.operation} answers "${key}" and the ledger neither stores it nor declines ` +
        "it in UNSTORED_KEYS - data dropped on the floor, or a column that was never added",
    );
  }
  return issues;
}

/**
 * A pass walks positions; it never sends a filter.
 *
 * Every operation here seeds optional caller inputs beside its paging keys -
 * `change_date`, `changed_from`, `last_updated_from`, `update_date`, a product
 * name, a licence number. Each reads a *subset*, and a subset is not a ledger:
 * a job that sent `change_date` would import what changed since a date and
 * call the ledger whole. The temptation is real - measured on
 * `search-food-item-report`, the unfiltered walk is capped at 100 calls an hour
 * (`INFO-320`) and the date filter is not - and the answer is to pay the quota
 * in hours, which the walk's quota wait exists for.
 *
 * So the window a walk sends holds the paging family's keys and nothing the
 * seed lists as a caller input. Read as dict-key syntax (`"key":`), because the
 * job's docstring names the filters it refuses.
 */
function checkMigrationWalksPositions(file: string, content: string, feeds: LedgerFeed[]): string[] {
  const paging = new Set(["range_start", "range_end", "page_no", "num_of_rows"]);
  const issues: string[] = [];
  const inputs = listIntegrationCallerInputs();
  for (const feed of feeds) {
    for (const key of inputs.get(feed.operation) ?? []) {
      if (paging.has(key)) continue;
      if (!new RegExp(`"${key}"\\s*:`).test(content)) continue;
      issues.push(
        `app/batch/${file}: sends "${key}" to ${feed.operation} - a filter reads a subset, and a ` +
          "ledger is everything; a pass is windows of PAGE_SIZE from row 1, never a date",
      );
    }
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
