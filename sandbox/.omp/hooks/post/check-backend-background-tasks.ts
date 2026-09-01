/**
 * Check-Backend-BackgroundTasks Post Hook
 *
 * Validates backend-background-tasks.md: BackgroundTasks pattern, no raw asyncio.create_task in routers
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendBackgroundTasks(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-background-tasks", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendBackgroundTasksSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-background-tasks");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-background-tasks",
      issues,
      "run make check-backend-background-tasks for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-background-tasks") };
  }));
}

function checkBackendBackgroundTasksSync(): string[] {
  const issues: string[] = [];

  // `ast-grep/rules/background/create-task.yml` owns "no raw asyncio.create_task":
  // one owner per invariant (omp-ast-rules.md). What remains here is the
  // cross-statement claim a pattern cannot make — an import without a call.
  const infraRules = join(projectRoot, ".omp", "ast-grep", "rules", "background");
  if (existsSync(infraRules)) {
    issues.push(...runAstRules(infraRules, [join(appDir, "routers")]));
  }
  const routersDir = join(appDir, "routers");
  if (!existsSync(routersDir)) return issues;
  const usesBackgroundTasks = readdirSync(routersDir)
    .filter((file: string) => file.endsWith(".py"))
    .some((file: string) => readFileSync(join(routersDir, file), "utf-8").includes("BackgroundTasks"));
  if (!usesBackgroundTasks) {
    return dormant("check-backend-background-tasks", "no BackgroundTasks usage in app/routers");
  }

  for (const f of readdirSync(routersDir)) {
    if (!f.endsWith(".py")) continue;
    const content = readFileSync(join(routersDir, f), "utf-8");
    if (/BackgroundTasks/.test(content) && !/background_tasks\.add_task/.test(content)) {
      issues.push(`${f}: BackgroundTasks imported but add_task never called`);
    }
  }
  return issues;
}

// Direct execution (make check-backend-background-tasks): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-background-tasks.ts")) {
  const issues = checkBackendBackgroundTasksSync();
  console.log("==> check-backend-background-tasks");
  if (issues.length === 0) {
    console.log(passLine("check-backend-background-tasks", "backend background-tasks standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-background-tasks");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
