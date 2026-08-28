/**
 * Check-Backend-Sse Post Hook
 *
 * Validates backend-sse.md: EventSourceResponse (fastapi.sse), AsyncIterable return
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendSse(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-sse", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendSseSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-sse");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-sse",
      issues,
      "run make check-backend-sse for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-sse") };
  }));
}

function checkBackendSseSync(): string[] {
  const issues: string[] = [];

  // AST rules — sse-streaming-response.yml (structural check)
  const infraRules = join(projectRoot, ".omp", "ast-grep", "rules", "sse");
  if (existsSync(infraRules)) {
    issues.push(...runAstRules(infraRules, [join(appDir, "routers")]));
  }
  const routersDir = join(appDir, "routers");
  if (!existsSync(routersDir)) return issues;
  const sseFiles = readdirSync(routersDir)
    .filter((file: string) => file.endsWith(".py"))
    .filter((file: string) =>
      /text\/event-stream|EventSourceResponse/.test(readFileSync(join(routersDir, file), "utf-8")),
    );
  if (sseFiles.length === 0) {
    return dormant("check-backend-sse", "no SSE endpoint in app/routers");
  }

  for (const f of readdirSync(routersDir)) {
    if (!f.endsWith(".py")) continue;
    const content = readFileSync(join(routersDir, f), "utf-8");
    // `ast-grep/rules/sse/streaming-response.yml` owns "no raw StreamingResponse".
    // The claims left here are about the generator's type and yielded value —
    // neither is a single node a pattern can point at.
    if (!/text\/event-stream|EventSourceResponse/.test(content)) continue;

    if (!/AsyncIterable/.test(content)) {
      issues.push(`${f}: SSE generator must declare AsyncIterable[ServerSentEvent] return type`);
    }
    if (!/ServerSentEvent/.test(content)) {
      issues.push(`${f}: SSE must yield ServerSentEvent (data/event/id/retry/comment)`);
    }
  }
  return issues;
}

// Direct execution (make check-backend-sse): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-sse.ts")) {
  const issues = checkBackendSseSync();
  console.log("==> check-backend-sse");
  if (issues.length === 0) {
    console.log(passLine("check-backend-sse", "backend sse standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-sse");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
