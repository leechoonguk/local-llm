/**
 * Check-Backend-Integration-Configuration Post Hook
 *
 * After tool execution, validates the database-managed external API
 * configuration standard (.omp/rules/backend-integration-configuration.md):
 * the four tables, DB resolution, request JSON Schema, named secrets resolved
 * through the field FK and never echoed, MAPPED/PASSTHROUGH response modes,
 * seed migrations, and the external API contract tests.
 *
 * The check logic lives in lib/backend-integration-configuration.ts so the rule
 * and the hook cannot drift apart.
 */
// @ts-ignore — OMP runtime module, not project-compiled
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
import { checkIntegrationConfiguration } from "../lib/backend-integration-configuration.ts";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

declare const process: {
  argv: string[];
  exit(code?: number): never;
};

const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkBackendIntegrationConfiguration(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-integration-configuration", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkIntegrationConfiguration();
    if (issues.length === 0) {
      resetSuppression("check-backend-integration-configuration");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-integration-configuration",
      issues,
      "run make check-backend-integration-configuration for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-integration-configuration") };
  }));
}

if (
  typeof process !== "undefined" &&
  process.argv[1]?.endsWith("check-backend-integration-configuration.ts")
) {
  const issues = checkIntegrationConfiguration();
  console.log("==> check-backend-integration-configuration");
  if (issues.length === 0) {
    console.log("    PASS: database-managed integration configuration standard valid");
    process.exit(0);
  }
  for (const issue of issues) console.log(`    FAIL: ${issue}`);
  printRuleHint("check-backend-integration-configuration");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
