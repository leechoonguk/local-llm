/**
 * Check-Backend-RateLimit Post Hook
 *
 * Validates backend-rate-limit.md: slowapi limiter on login/signup
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";

const projectRoot = resolveProjectRoot();
const appDir = join(projectRoot, "backend", "app");

export default function checkBackendRateLimit(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-rate-limit", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

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
  const routersDir = join(appDir, "routers");
  const authPath = join(routersDir, "auth.py");
  const userPath = join(routersDir, "user.py");
  const auth = existsSync(authPath) ? readFileSync(authPath, "utf-8") : "";
  const user = existsSync(userPath) ? readFileSync(userPath, "utf-8") : "";

  // Every router, not two: a limiter added to any endpoint carries the same 429
  // obligation, and scoping the search to auth.py/user.py meant a limiter
  // anywhere else was unguarded — measured with a planted `@limiter.limit` in
  // batch.py, which this check reported as dormant.
  const routers = existsSync(routersDir)
    ? readdirSync(routersDir)
        .filter((file: string) => file.endsWith(".py"))
        .map((file: string) => ({ file, content: readFileSync(join(routersDir, file), "utf-8") }))
    : [];
  const limited = routers.filter((router: { file: string; content: string }) => /@limiter\.limit|slowapi/.test(router.content));

  if (limited.length === 0) {
    return dormant("check-backend-rate-limit", "no slowapi limiter in app/routers");
  }

  const limitedText = limited.map((router: { file: string; content: string }) => router.content).join("\n");

  if (!/@limiter\.limit/.test(auth)) {
    issues.push("auth.py: @limiter.limit missing on POST /auth/login");
  }
  if (!/@limiter\.limit/.test(user)) {
    issues.push("user.py: @limiter.limit missing on POST /user/ (signup)");
  }
  // A 429 without Retry-After tells the client to back off for an unknown
  // time; Retry-After without 429 is unreachable. Both, separately.
  if (!/429/.test(limitedText)) {
    issues.push(
      `${limited.map((router: { file: string; content: string }) => router.file).join(", ")}: rate-limited endpoints must answer 429 when exceeded`,
    );
  }
  if (!/Retry-After/.test(limitedText)) {
    issues.push(
      `${limited.map((router: { file: string; content: string }) => router.file).join(", ")}: the 429 response must carry a Retry-After header`,
    );
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
