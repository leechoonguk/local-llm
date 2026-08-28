import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { checkDomainNaming } from "../lib/backend-naming.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Naming Post Hook
 *
 * Validates backend-naming.md: file names, service variable names,
 * repository encapsulation, module-private functions.
 *
 *   - AST rules: naming/ (var-name, repository-access)
 *   - lib: checkDomainNaming (module-private functions, conftest registration)
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendNaming(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-naming", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendNamingSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-naming");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-naming",
      issues,
      "run make check-backend-naming for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-naming") };
  }));
}

function checkBackendNamingSync(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  // AST rules — naming dir (code-wide scan).
  const namingRules = join(projectRoot, ".omp", "ast-grep", "rules", "naming");
  if (existsSync(namingRules)) {
    issues.push(
      ...runAstRules(namingRules, [
        join(base, "services"),
        join(base, "repositories"),
        join(base, "routers"),
        join(base, "batch"),
      ]),
    );
  }

  // lib — module-private functions + conftest registration.
  issues.push(...checkDomainNaming());

  return issues;
}

// Direct execution (make check-backend-naming): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-naming.ts")) {
  const issues = checkBackendNamingSync();
  console.log("==> check-backend-naming");
  if (issues.length === 0) {
    console.log("    PASS: backend naming conventions valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-naming");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
