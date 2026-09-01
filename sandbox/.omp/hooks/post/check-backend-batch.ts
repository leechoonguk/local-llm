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

    // 5. Must be an async function (batch jobs are async def)
    if (!/async def /.test(content)) {
      issues.push(`${f}: batch job must be an async def function`);
    }
  }

  // --- Scheduler registration: a job that cannot be identified cannot be replaced ---
  // A reload without `id`/`replace_existing` stacks a second copy; without
  // `max_instances=1` two runs delete the same rows; without `coalesce` +
  // `misfire_grace_time` a restart across the scheduled minute skips the run
  // entirely, silently.
  const mainPath = join(projectRoot, "backend", "app", "main.py");
  if (existsSync(mainPath)) {
    const main = readFileSync(mainPath, "utf-8");
    for (const block of main.split("add_job(").slice(1)) {
      const call = block.slice(0, block.indexOf("\n        )"));
      for (const [option, why] of [
        ["id=", "a job with no id cannot be replaced or inspected"],
        ["replace_existing=True", "a reload otherwise stacks a second copy of the job"],
        ["max_instances=1", "two overlapping runs act on the same rows"],
        ["coalesce=True", "a backlog otherwise fires once per missed interval"],
        ["misfire_grace_time=", "a restart across the scheduled minute otherwise skips the run"],
      ]) {
        if (!call.includes(option)) {
          issues.push(`main.py: scheduler add_job is missing \`${option}\` — ${why}`);
        }
      }
    }
  }

  return issues;
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
