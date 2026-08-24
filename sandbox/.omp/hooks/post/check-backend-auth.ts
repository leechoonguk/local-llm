import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { checkDomainAuth } from "../lib/backend-auth.ts";
import { guarded } from "../lib/hook-visibility.ts";

/**
 * Check-Backend-Auth Post Hook
 *
 * Validates backend-auth.md: JWT auth, current_user injection, domain
 * exception patterns.
 *
 *   - AST rules: router/ (write-auth, auth-all, inline-depends, response-model),
 *     service/ (http-exception), conventions/ (current-user-router-only)
 *   - lib: checkDomainAuth (exception handlers + service domain exceptions)
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendAuth(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-auth", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendAuthSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-auth");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-auth",
      issues,
      "run make check-backend-auth for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-auth") };
  }));
}

function checkBackendAuthSync(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  // AST rules — auth-related dirs.
  const routerRules = join(projectRoot, ".omp", "ast-grep", "rules", "router");
  if (existsSync(routerRules)) {
    issues.push(...runAstRules(routerRules, [join(base, "routers")]));
  }
  // CPU-bound work in an async request path is an availability bug, not a style
  // one — the rule runs against the layers that serve requests.
  const offloadRules = join(projectRoot, ".omp", "ast-grep", "rules", "offload");
  if (existsSync(offloadRules)) {
    issues.push(...runAstRules(offloadRules, [join(base, "routers"), join(base, "services")]));
  }
  const actorRules = join(projectRoot, ".omp", "ast-grep", "rules", "auth");
  if (existsSync(actorRules)) {
    issues.push(...runAstRules(actorRules, [join(base, "routers"), join(base, "services")]));
  }
  const serviceRules = join(projectRoot, ".omp", "ast-grep", "rules", "service");
  if (existsSync(serviceRules)) {
    issues.push(...runAstRules(serviceRules, [join(base, "services")]));
  }
  // conventions/ contains the auth-specific current-user rule.
  // Naming-only conventions are owned by check-backend-naming.ts.
  const conventionsRules = join(projectRoot, ".omp", "ast-grep", "rules", "conventions");
  if (existsSync(conventionsRules)) {
    issues.push(
      ...runAstRules(conventionsRules, [
        join(base, "services"),
        join(base, "repositories"),
        join(base, "core"),
        join(base, "dependencies"),
        join(base, "models"),
        join(base, "schemas"),
        join(base, "batch"),
      ]),
    );
  }

  // lib — exception handlers + service domain exceptions.
  issues.push(...checkDomainAuth());

  return issues;
}

// Direct execution (make check-backend-auth): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-auth.ts")) {
  const issues = checkBackendAuthSync();
  console.log("==> check-backend-auth");
  if (issues.length === 0) {
    console.log("    PASS: backend auth conventions valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
