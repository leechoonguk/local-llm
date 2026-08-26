import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Frontend-Code Post Hook
 *
 * After tool execution, validates the frontend code conventions in
 * .omp/rules/frontend-code-conventions.md:
 *   1. Required src/ files exist: main.tsx, App.tsx, styles.css
 *   2. No class components (functional only)
 *   3. `@/` alias used for imports inside src/
 *   4. fetch calls check res.ok
 *   5. No hardcoded port numbers in components
 *
 * Lint/typecheck/build are delegated to check-verify.ts — this hook only
 * covers structural conventions that ESLint/tsc do not enforce.
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
const cwd = process.cwd();
// Adjust cwd to project root if running from frontend/
const projectRoot = existsSync(join(cwd, "frontend", "src")) ? cwd : join(cwd, "..");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkFrontendCode(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-code", event, () => {
    // Skip read-only tools — they cannot change frontend files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendCodeSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-code"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-code",
      issues,
      "run make check-frontend-code for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-code") };
  }));
}

function checkFrontendCodeSync(): string[] {
  const issues: string[] = [];
  const srcDir = join(projectRoot, "frontend", "src");

  if (!existsSync(srcDir)) {
    issues.push("frontend/src/ directory not found");
    return issues;
  }

  // --- 1. Required files ---
  for (const required of ["main.tsx", "App.tsx", "styles.css"]) {
    if (!existsSync(join(srcDir, required))) {
      issues.push(`missing required file src/${required}`);
    }
  }

  // --- 2-5. Content checks on .tsx files ---
  for (const f of readdirSync(srcDir)) {
    if (!f.endsWith(".tsx")) continue;
    const content = readFileSync(join(srcDir, f), "utf-8");

    // 2. No class components
    if (/\bclass\s+\w+\s+extends\s+(?:React\.)?(?:Component|PureComponent)\b/.test(content)) {
      issues.push(`${f}: class components forbidden — use functional components`);
    }

    // 3. @/ alias for imports inside src/ (relative imports of src files)
    //    e.g. `from './errors'` → `from '@/errors'`
    for (const m of content.matchAll(/from\s+['"]\.\.?\/[^'"]+['"]/g)) {
      issues.push(`${f}: relative import ${m[0]} — use @/ alias inside src/`);
    }

    // 4. fetch must check res.ok
    if (/fetch\s*\(/.test(content) && !/\.ok\b/.test(content)) {
      issues.push(`${f}: fetch call without res.ok check`);
    }

    // 5. No hardcoded port numbers in components
    if (/:\d{4,5}\b/.test(content)) {
      issues.push(`${f}: hardcoded port number — use Vite config proxy instead`);
    }
  }

  return issues;
}

// Direct execution (make check-frontend-code): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-code.ts")) {
  const issues = checkFrontendCodeSync();
  console.log("==> check-frontend-code");
  if (issues.length === 0) {
    console.log("    PASS: frontend code follows frontend-code-conventions.md");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-code");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
