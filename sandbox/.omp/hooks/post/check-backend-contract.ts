import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";
import { collectBackendReachability } from "../lib/backend-reachability.ts";

/**
 * Check-Backend-Contract Post Hook
 *
 * The backend half of `check-frontend-contract`. That check refuses a transport
 * function no hook calls and a hook no screen renders; this one refuses backend
 * surface nothing in `app/` can reach:
 *
 *   1. a `*ServiceDep` alias declared and injected into no endpoint
 *   2. a public service/repository method beyond the CRUD template with no
 *      caller anywhere in `app/`
 *
 * Tests are not callers. A method whose only caller is its own test is the
 * definition of the thing both checks exist to catch — code that looks finished
 * from inside its layer and is reachable from nothing that runs.
 *
 * The template's own methods (`get`/`list`/`create`/`update`/`delete`) are left
 * alone: `rule://backend-domain` requires them of every domain, router or not,
 * so their existence is explained by the shape rather than by a caller.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const projectRoot = resolveProjectRoot();

export default function checkBackendContract(pi: ExtensionAPI): void {
  pi.on(
    "tool_result",
    (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) =>
      guarded("check-backend-contract", event, () => {
        if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
        if (!touchesPath(event, ["backend/"])) return;

        const issues = checkBackendContractSync();
        if (issues.length === 0) {
          resetSuppression("check-backend-contract");
          return;
        }
        const warning = buildSafeWarning(
          event.toolName,
          "check-backend-contract",
          issues,
          "run make check-backend-contract for details",
        );
        if (warning === null) return;
        console.error(warning);
        return { content: wrapWarning(warning, event.content, "check-backend-contract") };
      }),
  );
}

function checkBackendContractSync(): string[] {
  return collectBackendReachability(projectRoot).map((dead) => `${dead.label}: ${dead.detail}`);
}

// Direct execution (make check-backend-contract): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-contract.ts")) {
  const issues = checkBackendContractSync();
  console.log("==> check-backend-contract");
  if (issues.length === 0) {
    console.log("    PASS: every backend surface is reachable from an entry point");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-contract");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
