import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { runAstRules } from "../lib/ast-rules.ts";
import { aggregateDomains, belongsToAggregateDomain, checkDomainStructure, checkRelationshipLoading } from "../lib/backend-domain-structure.ts";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Domain Post Hook
 *
 * Validates backend-domain.md: 5-layer CRUD structure.
 *
 *   - AST rules: model/ (id-standard, field-mapped-pattern)
 *   - lib: checkDomainStructure (5-layer existence + contents)
 *
 * ORM ↔ DB sync lives in check-backend-migrations.ts (backend-migrations.md).
 * Auth/api-http/naming/transaction checks live in their own hooks.
 * This is a read-only check — it does NOT block tool calls.
 *
 * Uses hook-safety-guard to prevent infinite loops:
 *   - Warning truncated to 3 issue lines
 *   - Content protection: long tool output → 1-line summary
 *   - Per-tool suppression: max 2 repeats before silencing
 */
const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkBackendDomain(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-domain", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendDomainSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-domain");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-domain",
      issues,
      "ensure 5-layer CRUD pattern (backend-domain.md) — run make check-backend-domain",
    );
    if (warning === null) return; // suppressed — agent is stuck
    console.error(warning);
    return {
      content: wrapWarning(warning, event.content, "check-backend-domain"),
    };
  }));
}

function checkBackendDomainSync(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  // AST rules apply to simple CRUD models. A multi-table aggregate contains
  // SQLAlchemy relationships and is validated by its dedicated configuration
  // hook — excluded by measure (aggregateDomains), never by filename: the
  // hardcoded `integration.py` skip is what silently stopped matching in
  // fast-api-standard the day that file became five files.
  // (fast-api-standard 쪽은 field-mapped-pattern.yml 이 relationship() 을 알아 무필터로 돌린다 —
  // 이 트리의 yml 은 아직 몰라서 측정 필터를 유지한다. 트리별 차이 2026-08-31.)
  const modelRules = join(projectRoot, ".omp", "ast-grep", "rules", "model");
  const modelsDir = join(base, "models");
  if (existsSync(modelRules) && existsSync(modelsDir)) {
    const aggregates = aggregateDomains();
    const modelPaths = readdirSync(modelsDir)
      .filter((file: string) => file.endsWith(".py") && !belongsToAggregateDomain(file.replace(/\.py$/, ""), aggregates))
      .map((file: string) => join(modelsDir, file));
    issues.push(...runAstRules(modelRules, modelPaths));
  }

  // Layer skipping is visible at the import: a router that names a repository
  // can reach rows without the service that owns them.
  const layeringRules = join(projectRoot, ".omp", "ast-grep", "rules", "layering");
  if (existsSync(layeringRules)) {
    issues.push(...runAstRules(layeringRules, [join(base, "routers")]));
  }
  const factoryRules = join(projectRoot, ".omp", "ast-grep", "rules", "factory");
  if (existsSync(factoryRules)) {
    issues.push(...runAstRules(factoryRules, [base]));
  }

  issues.push(...checkRelationshipLoading(base));

  // lib — 5-layer structure.
  issues.push(...checkDomainStructure());

  return issues;
}

// Direct execution (make check-backend-domain): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-domain.ts")) {
  const issues = checkBackendDomainSync();
  console.log("==> check-backend-domain");
  if (issues.length === 0) {
    console.log("    PASS: all backend CRUD domains follow the 5-layer pattern");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-domain");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
