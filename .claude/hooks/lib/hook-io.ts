/**
 * hook-io.ts — Claude Code 훅 프로토콜(공식 문서 https://code.claude.com/docs/en/hooks.md 기준).
 *
 *  - stdin: JSON. 공통 `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`(Edit/Write 는
 *    `file_path`, Bash 는 `command`), PostToolUse 는 `tool_response` 추가.
 *  - exit 0 + stdout JSON → 결정. PreToolUse 는 `hookSpecificOutput.permissionDecision: "deny"` 와
 *    `permissionDecisionReason`. PostToolUse 는 `hookSpecificOutput.additionalContext` 로 문맥을 얹는다.
 *  - exit 2 → 차단 오류. stderr 가 모델에 전달된다(PostToolUse 에선 도구는 이미 실행됐고 결과만 알린다).
 *  - 그 외 exit → 비차단 오류, 진행. 훅 자체의 버그는 이 경로로 새지 않게 잡아서 exit 0 으로 낸다.
 */
import { readFileSync } from "node:fs";

export type HookInput = {
  session_id?: string;
  cwd?: string;
  hook_event_name?: string;
  tool_name?: string;
  tool_input?: { file_path?: string; command?: string; [k: string]: unknown };
  tool_response?: unknown;
};

export function readHookInput(): HookInput {
  try {
    const raw = readFileSync(0, "utf-8");
    return raw.trim() === "" ? {} : (JSON.parse(raw) as HookInput);
  } catch { return {}; }
}

export function deny(event: "PreToolUse", reason: string): never {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: event, permissionDecision: "deny", permissionDecisionReason: reason } }));
  process.exit(0);
}
export function addContext(event: "PostToolUse", text: string): never {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: event, additionalContext: text } }));
  process.exit(0);
}

/** 위반을 모델에 알린다(exit 2, stderr). PostToolUse 전용. */
export function block(lines: string[]): never {
  process.stderr.write(lines.join("\n") + "\n");
  process.exit(2);
}

/** 훅 본체를 감싼다: 훅의 예외는 stderr 한 줄 + exit 0 (다른 훅과 도구 호출을 죽이지 않는다). */
export function guarded(name: string, fn: () => void | Promise<void>): void {
  const fail = (e: unknown) => {
    process.stderr.write(`[${name}] 훅 자체가 실패했다 — ${(e as Error).stack ?? String(e)}\n`);
    process.exit(0);
  };
  try { const r = fn(); if (r && typeof (r as Promise<void>).catch === "function") (r as Promise<void>).catch(fail); }
  catch (e) { fail(e); }
}
