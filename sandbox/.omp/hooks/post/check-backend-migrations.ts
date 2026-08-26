import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { checkOrmDbSync, lastSkipReason } from "../lib/backend-orm-sync.ts";
import { checkMigrationPolicy } from "../lib/backend-migration-policy.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Migrations Post Hook
 *
 * Validates backend-migrations.md: ORM ↔ DB sync via `alembic check` plus
 * one-table unpushed revisions and immutability of upstream migrations.
 *
 *   - lib: checkOrmDbSync
 *
 * This is a read-only check — it does NOT block tool calls.
 */

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkBackendMigrations(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: {
    toolName?: string;
    input?: Record<string, unknown>;
    content?: Array<{ type: string; text?: string }>;
  }) => guarded("check-backend-migrations", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (isMigrationCommand(event.input)) {
      resetSuppression("check-backend-migrations");
      return;
    }

    const issues = checkBackendMigrationsSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-migrations");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-migrations",
      issues,
      "run make check-backend-migrations for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-migrations") };
  }));
}

function isMigrationCommand(input: Record<string, unknown> | undefined): boolean {
  const command = String(input?.command ?? "");
  return /\bmake(?:\s+-C\s+\S+)?\s+(?:migrate(?:-gen)?|downgrade)\b/.test(command);
}

function checkBackendMigrationsSync(): string[] {
  return [...checkOrmDbSync(), ...checkMigrationPolicy()];
}

// Direct execution (make check-backend-migrations): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-migrations.ts")) {
  const issues = checkBackendMigrationsSync();
  console.log("==> check-backend-migrations");
  if (issues.length === 0) {
    // A pass is a claim about a comparison. When `alembic check` could not run,
    // say which comparison is missing — a green line here once hid a real added
    // column because DATABASE_URL pointed at an unresolvable host.
    if (lastSkipReason !== null) dormant("check-backend-migrations", lastSkipReason);
    console.log(passLine("check-backend-migrations", "ORM/DB in sync"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-migrations");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
