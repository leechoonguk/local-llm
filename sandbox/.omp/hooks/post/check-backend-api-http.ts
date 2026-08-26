import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { checkDomainApiHttp } from "../lib/backend-api-http.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Api-Http Post Hook
 *
 * Validates backend-api-http.md: router ↔ api/*.http sync (bidirectional)
 * and the .http content standard (@base, login block, Bearer token).
 *
 *   - lib: checkDomainApiHttp
 *
 * This is a read-only check — it does NOT block tool calls.
 */

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendApiHttp(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-api-http", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendApiHttpSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-api-http");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-api-http",
      issues,
      "run make check-backend-api-http for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-api-http") };
  }));
}

function checkBackendApiHttpSync(): string[] {
  return checkDomainApiHttp();
}

// Direct execution (make check-backend-api-http): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-api-http.ts")) {
  const issues = checkBackendApiHttpSync();
  console.log("==> check-backend-api-http");
  if (issues.length === 0) {
    console.log("    PASS: router ↔ .http sync valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-api-http");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
