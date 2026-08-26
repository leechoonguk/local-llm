/**
 * Check-Backend-RateLimit Post Hook
 *
 * Validates backend-rate-limit.md: slowapi limiter on login/signup
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendRateLimit(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-rate-limit", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendRateLimitSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-rate-limit");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-rate-limit",
      issues,
      "run make check-backend-rate-limit for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-rate-limit") };
  }));
}

function checkBackendRateLimitSync(): string[] {
  const issues: string[] = [];
  const authPath = join(appDir, "routers", "auth.py");
  const userPath = join(appDir, "routers", "user.py");
  const auth = existsSync(authPath) ? readFileSync(authPath, "utf-8") : "";
  const user = existsSync(userPath) ? readFileSync(userPath, "utf-8") : "";

  // Only check when the limiter is actually used somewhere.
  const limiterUsed = /limiter|slowapi/.test(auth + user);
  if (!limiterUsed) {
    return dormant("check-backend-rate-limit", "no slowapi limiter in auth.py/user.py");
  }

  if (!/@limiter\.limit/.test(auth)) {
    issues.push("auth.py: @limiter.limit missing on POST /auth/login");
  }
  if (!/@limiter\.limit/.test(user)) {
    issues.push("user.py: @limiter.limit missing on POST /user/ (signup)");
  }
  // A 429 without Retry-After tells the client to back off for an unknown
  // time; Retry-After without 429 is unreachable. Both, separately.
  if (!/429/.test(auth + user)) {
    issues.push("auth.py/user.py: rate-limited endpoints must answer 429 when exceeded");
  }
  if (!/Retry-After/.test(auth + user)) {
    issues.push("auth.py/user.py: the 429 response must carry a Retry-After header");
  }
  return issues;
}

// Direct execution (make check-backend-rate-limit): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-rate-limit.ts")) {
  const issues = checkBackendRateLimitSync();
  console.log("==> check-backend-rate-limit");
  if (issues.length === 0) {
    console.log(passLine("check-backend-rate-limit", "backend rate-limit standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-rate-limit");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
