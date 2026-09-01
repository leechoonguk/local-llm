/**
 * Check-Backend-ApiKeys Post Hook
 *
 * Validates backend-api-keys.md: X-API-Key dependency, distinct from JWT
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendApiKeys(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-api-keys", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendApiKeysSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-api-keys");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-api-keys",
      issues,
      "run make check-backend-api-keys for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-api-keys") };
  }));
}

function checkBackendApiKeysSync(): string[] {
  const issues: string[] = [];
  const apiKeyPath = join(appDir, "dependencies", "api_key.py");
  if (!existsSync(apiKeyPath)) {
    return dormant("check-backend-api-keys", "no app/dependencies/api_key.py");
  }
  const apiKey = readFileSync(apiKeyPath, "utf-8");

  // The header name is the contract; a variable called `api_key` is not.
  if (!/X-API-Key/.test(apiKey)) {
    issues.push("api_key.py: X-API-Key header dependency required");
  }
  // The model class is the contract; the table name follows from it.
  if (!/ServiceAccount/.test(apiKey)) {
    issues.push("api_key.py: ServiceAccount model required (distinct from user JWT)");
  }
  return issues;
}

// Direct execution (make check-backend-api-keys): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-api-keys.ts")) {
  const issues = checkBackendApiKeysSync();
  console.log("==> check-backend-api-keys");
  if (issues.length === 0) {
    console.log(passLine("check-backend-api-keys", "backend api-keys standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-api-keys");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
