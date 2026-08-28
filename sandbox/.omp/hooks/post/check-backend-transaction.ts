import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Transaction Post Hook
 *
 * Validates backend-transaction.md: session.begin() placement rules.
 *
 *   - AST rules: transaction/ (service-only), domain/ (service-transaction-write-only)
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendTransaction(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-transaction", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendTransactionSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-transaction");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-transaction",
      issues,
      "run make check-backend-transaction for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-transaction") };
  }));
}

function checkBackendTransactionSync(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  // transaction/ — session.begin() forbidden outside services (incl. batch).
  const transactionRules = join(projectRoot, ".omp", "ast-grep", "rules", "transaction");
  if (existsSync(transactionRules)) {
    issues.push(
      ...runAstRules(transactionRules, [
        join(base, "repositories"),
        join(base, "routers"),
        join(base, "core"),
        join(base, "dependencies"),
        join(base, "models"),
        join(base, "schemas"),
        join(base, "batch"),
      ]),
    );
  }

  // domain/ — within simple CRUD services, only create/update/delete may open
  // a transaction. The integration aggregate has synchronous validation helpers
  // and relationship replacement validated by its dedicated configuration hook.
  const domainRules = join(projectRoot, ".omp", "ast-grep", "rules", "domain");
  if (existsSync(domainRules)) {
    const aggregatePaths = ["services", "repositories"].flatMap((directory) => {
      const directoryPath = join(base, directory);
      return readdirSync(directoryPath)
        .filter((file: string) => file.endsWith(".py") && file !== "integration.py")
        .map((file: string) => join(directoryPath, file));
    });
    issues.push(...runAstRules(domainRules, aggregatePaths));
  }

  return issues;
}

// Direct execution (make check-backend-transaction): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-transaction.ts")) {
  const issues = checkBackendTransactionSync();
  console.log("==> check-backend-transaction");
  if (issues.length === 0) {
    console.log("    PASS: backend transaction conventions valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-transaction");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
