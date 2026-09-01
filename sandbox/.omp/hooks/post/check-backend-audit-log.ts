/**
 * Check-Backend-AuditLog Post Hook
 *
 * Validates backend-audit-log.md: read-only audit endpoint, no internal fields
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
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";

const projectRoot = resolveProjectRoot();
const appDir = join(projectRoot, "backend", "app");

export default function checkBackendAuditLog(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-audit-log", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendAuditLogSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-audit-log");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-audit-log",
      issues,
      "run make check-backend-audit-log for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-audit-log") };
  }));
}

function checkBackendAuditLogSync(): string[] {
  const issues: string[] = [];

  // `ast-grep/rules/audit/exposes-secret.yml` owns "never expose hashed_password".
  const infraRules = join(projectRoot, ".omp", "ast-grep", "rules", "audit");
  if (existsSync(infraRules)) {
    issues.push(...runAstRules(infraRules, [join(appDir, "routers")]));
  }
  const auditPath = join(appDir, "routers", "audit.py");
  const readOnlyRules = join(projectRoot, ".omp", "ast-grep", "rules", "audit-readonly");
  if (existsSync(auditPath) && existsSync(readOnlyRules)) {
    issues.push(...runAstRules(readOnlyRules, [auditPath]));
  }
  if (!existsSync(auditPath)) {
    return dormant("check-backend-audit-log", "no app/routers/audit.py");
  }
  const audit = readFileSync(auditPath, "utf-8");

  if (!/\/audit/.test(audit)) {
    issues.push("audit.py: no GET /audit endpoint");
  }
  // Both columns are the audit trail: exposing only one answers half the
  // question ("who changed this last?" vs "who created it?").
  if (!/created_by/.test(audit)) {
    issues.push("audit.py: must expose created_by");
  }
  if (!/updated_by/.test(audit)) {
    issues.push("audit.py: must expose updated_by");
  }
  return issues;
}

// Direct execution (make check-backend-audit-log): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-audit-log.ts")) {
  const issues = checkBackendAuditLogSync();
  console.log("==> check-backend-audit-log");
  if (issues.length === 0) {
    console.log(passLine("check-backend-audit-log", "backend audit-log standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-audit-log");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
