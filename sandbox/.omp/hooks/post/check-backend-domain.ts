import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { runAstRules } from "../lib/ast-rules.ts";
import { checkDomainStructure, checkRelationshipLoading } from "../lib/backend-domain-structure.ts";
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

  // AST rules apply to simple CRUD models. The integration aggregate contains
  // SQLAlchemy relationships and is validated by its dedicated configuration hook.
  const modelRules = join(projectRoot, ".omp", "ast-grep", "rules", "model");
  const modelsDir = join(base, "models");
  if (existsSync(modelRules) && existsSync(modelsDir)) {
    const modelPaths = readdirSync(modelsDir)
      .filter((file: string) => file.endsWith(".py") && file !== "integration.py")
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
