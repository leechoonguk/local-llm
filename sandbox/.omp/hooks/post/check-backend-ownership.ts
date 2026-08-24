/**
 * Check-Backend-Ownership Post Hook
 *
 * Validates backend-ownership.md: created_by verification on user-scoped resources
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendOwnership(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-ownership", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendOwnershipSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-ownership");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-ownership",
      issues,
      "run make check-backend-ownership for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-ownership") };
  }));
}

function checkBackendOwnershipSync(): string[] {
  const issues: string[] = [];

  // `ast-grep/rules/ownership/check-missing.yml` is the sole owner: it reads the
  // parameter list and searches the whole function body structurally, which a
  // file-level regex could only approximate.
  const ownershipRules = join(projectRoot, ".omp", "ast-grep", "rules", "ownership");
  if (existsSync(ownershipRules)) {
    issues.push(...runAstRules(ownershipRules, [join(appDir, "services")]));
  }
  const routerRules = join(projectRoot, ".omp", "ast-grep", "rules", "ownership-router");
  if (existsSync(routerRules)) {
    issues.push(...runAstRules(routerRules, [join(appDir, "routers")]));
  }
  // Placement is checked even when the service side is dormant: a router that
  // does the comparison itself is exactly the case where no service method
  // takes current_user, so returning dormant first would hide it.
  const servicesDir = join(appDir, "services");
  const scoped = existsSync(servicesDir)
    ? readdirSync(servicesDir)
        .filter((file: string) => file.endsWith(".py"))
        .some((file: string) => readFileSync(join(servicesDir, file), "utf-8").includes("current_user"))
    : false;
  if (!scoped && issues.length === 0) {
    return dormant("check-backend-ownership", "no service method takes current_user");
  }
  return issues;
}

// Direct execution (make check-backend-ownership): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-ownership.ts")) {
  const issues = checkBackendOwnershipSync();
  console.log("==> check-backend-ownership");
  if (issues.length === 0) {
    console.log(passLine("check-backend-ownership", "backend ownership standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
