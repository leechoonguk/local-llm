import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { checkComponentSplitSync } from "../lib/frontend-component-split.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-Components Post Hook
 *
 * Validates the splitting rules from .omp/rules/frontend-components.md: one
 * section per shape, one component per concept, one screen per record. The
 * measurements, the thresholds and the reason two *screens* of one type are
 * allowed to look alike live in `lib/frontend-component-split.ts`.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkFrontendComponents(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-components", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkComponentSplitSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-components");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-components",
      issues,
      "run make check-frontend-components for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-components") };
  }));
}

// Direct execution (make check-frontend-components): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-components.ts")) {
  const issues = checkComponentSplitSync();
  console.log("==> check-frontend-components");
  if (issues.length === 0) {
    console.log("    PASS: no shape is written twice");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-components");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
