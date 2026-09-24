import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { checkRelationsSync } from "../lib/backend-relations.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Backend-Relations Post Hook
 *
 * Validates backend-relations.md: a join between two ledgers is a viewonly
 * `relationship()` on the model with an explicit `primaryjoin` — and nothing
 * joins ledgers by `ForeignKey` or by class in a query layer. The
 * measurement lives in `lib/backend-relations.ts`.
 *
 * This is a read-only check — it does NOT block tool calls.
 */

export default function checkBackendRelations(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-relations", event, () => {
    if (!touchesPath(event, ["backend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkRelationsSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-relations");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-relations",
      issues,
      "run make check-backend-relations for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-relations") };
  }));
}

// Direct execution (make check-backend-relations): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-relations.ts")) {
  const issues = checkRelationsSync();
  console.log("==> check-backend-relations");
  if (issues.length === 0) {
    console.log("    PASS: no ledger is an edge's endpoint; every edge is viewonly with its own primaryjoin");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-relations");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
