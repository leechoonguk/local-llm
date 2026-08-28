import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
};

/**
 * Check-Verify Post Hook
 *
 * Runs backend and frontend verification after a source-changing tool result.
 *
 * bash is deliberately NOT a trigger: `make <target>` already runs its own
 * quality gates, and running a competing `make verify` from the hook while
 * the agent's make runs would race pytest/ruff and produce transient
 * failures. Source changes happen through write/edit/ast_edit — those are
 * the triggers.
 */
const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) && existsSync(join(cwd, "frontend", "src"))
  ? cwd
  : existsSync(join(cwd, "..", "backend", "app")) && existsSync(join(cwd, "..", "frontend", "src"))
  ? join(cwd, "..")
  : cwd;

/**
 * Success is cheap to re-confirm later; a failure is not. Holding the same
 * 5-minute silence after a red verify meant the next five minutes of edits got
 * no feedback at all, so failure re-checks quickly.
 */
const THROTTLE_MS = 5 * 60 * 1000;
const FAILURE_THROTTLE_MS = 90 * 1000; // 실측 2026-08-29: 이 훅 1회가 1.8~7.7초(실제 make 실행)다.
// 30초 스로틀은 빨간 구간(셀 벽시계의 절반)에 게이트를 40회까지 밀어 넣어 모델이 가장 바쁠 때
// 하네스가 가장 무거워졌다. 90초면 같은 구간에서 13회 안팎 — 조기 발견은 남기고 증폭만 깎는다.
let lastRunAt = 0;
let lastRunFailed = false;

/** Lines worth quoting: what failed, not the 200 lines of progress before it. */
const DIAGNOSTIC_LINE = /FAILED|ERROR|error:|Error:|error TS|Coverage failure|assert|make: \*\*\*/;
const MAX_DIAGNOSTIC_LINES = 3;

const MUTATING_TOOLS = new Set([
  "write", "edit", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkVerify(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: {
    toolName?: string;
    input?: Record<string, unknown>;
    content?: Array<{ type: string; text?: string }>;
  }) => guarded("check-verify", event, () => {
    // hook-scope: global — 전체 게이트 — 무엇을 고쳤든 프로젝트 검증이 대상이다
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (isMakeCommand(event.input)) return;

    const now = Date.now();
    const throttle = lastRunFailed ? FAILURE_THROTTLE_MS : THROTTLE_MS;
    if (now - lastRunAt < throttle) return;
    lastRunAt = now;

    const issues = runVerify();
    lastRunFailed = issues.length > 0;
    if (issues.length === 0) {
      resetSuppression("check-verify");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-verify",
      issues,
      "run make check-verify for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-verify") };
  }));
}

function isMakeCommand(input: Record<string, unknown> | undefined): boolean {
  if (!input) return false;
  // Defensive: a make command on any triggering tool's input already ran its
  // own gates — never spawn a competing nested verify.
  return /^\s*make(?:\s|$)/.test(String(input.command ?? ""));
}

/**
 * The exit status alone ("make verify failed (exit 2)") sent every reader to run
 * the command by hand. The tail of the child's own output names the failing
 * test, rule or type error directly.
 */
function runMakeVerify(dir: string): string[] {
  const result = spawnSync("make", ["verify"], { cwd: dir, encoding: "utf-8" });
  if (result.status === 0) return [];

  const label = dir === projectRoot ? "root" : dir.split("/").pop();
  const output = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
  const diagnosis = output
    .split("\n")
    .filter((line: string) => DIAGNOSTIC_LINE.test(line))
    .slice(-MAX_DIAGNOSTIC_LINES)
    .map((line: string) => line.trim())
    .join(" | ");
  return [
    `${label}: make verify failed (exit ${result.status})` +
      (diagnosis === "" ? "" : ` — ${diagnosis}`),
  ];
}

function runVerify(): string[] {
  const issues: string[] = [];

  const backendDir = join(projectRoot, "backend");
  if (existsSync(join(backendDir, "Makefile"))) {
    issues.push(...runMakeVerify(backendDir));
  } else {
    issues.push("backend/Makefile: not found");
  }

  const frontendDir = join(projectRoot, "frontend");
  if (existsSync(join(frontendDir, "Makefile"))) {
    issues.push(...runMakeVerify(frontendDir));
  } else {
    issues.push("frontend/Makefile: not found");
  }

  return issues;
}

if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-verify.ts")) {
  const issues = runVerify();
  console.log("==> check-verify");
  if (issues.length === 0) {
    console.log("    PASS: backend + frontend make verify passed");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-verify");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
