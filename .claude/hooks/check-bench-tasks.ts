#!/usr/bin/env node
/**
 * 벤치 과제의 모양·이름 계약 검사 — `make check-bench-tasks`.
 *
 * 규칙 본문은 `.claude/rules/bench-tasks.md`. 넷을 본다.
 *
 *  1. 모든 과제가 `shape: "greenfield"` 인가 — 다른 모양(정답을 지우고 재현)은 채점을 뒤집고 지름길을 만든다.
 *  2. 기대 산출물(매니페스트 `added`)이 피험자 트리에 존재하지 않는가 — 있으면 그건 정답이 아니라 기준선이다.
 *  3. "Mode A/B" 어휘가 남아 있지 않은가 — 과제는 이름으로 부른다.
 *  4. `expect` 가 매니페스트의 `added + modified` 수와 같은가.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const SKILL = join(ROOT, ".claude", "skills", "llm-bench");
const RUNNER = join(SKILL, "runner.ts");
const REFERENCE = join(SKILL, "reference");
const SANDBOX = join(ROOT, "sandbox");

const issues: string[] = [];

// 벤치 셀 실행 중에는 피험자가 정답을 트리에 만들어 가는 중이다 — 그건 과제 수행이지
// 기준선 오염이 아니다(셀 종료 시 원복·채점). 셀 중에는 판정하지 않는다(2026-09-01).
import { execFileSync } from "node:child_process";
try {
  if (execFileSync("bash", ["-c", "pgrep -f 'omp -p' >/dev/null && echo 1 || true"], { encoding: "utf-8" }).trim() === "1") {
    console.log("check-bench-tasks: skip — 벤치 셀 실행 중(기준선 판정은 셀 종료 후)");
    process.exit(0);
  }
} catch { /* pgrep 불가 호스트 — 그대로 진행 */ }

if (!existsSync(RUNNER)) {
  console.log("check-bench-tasks: skip — llm-bench 러너 없음");
  process.exit(0);
}

const runner = readFileSync(RUNNER, "utf-8");

// --- 1. 모든 과제가 greenfield ---
// TASKS 블록 안의 과제 항목마다 shape 선언을 확인한다.
const tasksBlock = /const TASKS: Record<string, Task> = \{([\s\S]*?)\n\};/.exec(runner)?.[1] ?? "";
const taskNames = [...tasksBlock.matchAll(/^ {2}([a-z][a-z0-9_]*):\s*\{/gm)].map((m) => m[1]);
for (const name of taskNames) {
  const body = new RegExp(`^ {2}${name}:\\s*\\{([\\s\\S]*?)^ {2}\\},`, "m").exec(tasksBlock)?.[1] ?? "";
  if (!/shape:\s*"greenfield"/.test(body)) {
    issues.push(`과제 '${name}' 가 shape: "greenfield" 를 선언하지 않는다 — 모든 과제는 없는 것을 더하는 모양이다 (bench-tasks.md 1)`);
  }
}
if (taskNames.length === 0) issues.push("runner.ts 에서 TASKS 정의를 읽지 못했다 — 이 검사가 아무것도 보지 못한다");

// --- 2·4. 매니페스트: 정답이 트리에 없어야 하고, expect 와 수가 맞아야 한다 ---
if (existsSync(REFERENCE)) {
  for (const f of readdirSync(REFERENCE).filter((n) => n.endsWith(".manifest.json"))) {
    const ref = f.replace(/\.manifest\.json$/, "");
    let manifest: { added?: string[]; modified?: string[] };
    try {
      manifest = JSON.parse(readFileSync(join(REFERENCE, f), "utf-8")) as { added?: string[]; modified?: string[] };
    } catch (e) {
      issues.push(`reference/${f}: 읽을 수 없다 — ${String(e).slice(0, 60)}`);
      continue;
    }
    const added = manifest.added ?? [];
    for (const rel of added) {
      if (existsSync(join(SANDBOX, rel))) {
        issues.push(`reference/${f} 의 기대 산출물이 피험자 트리에 있다: sandbox/${rel} — 정답은 reference/answers/ 에 두고 트리에서는 빼야 과제가 성립한다 (bench-tasks.md 2)`);
      }
    }
    // 프롬프트↔매니페스트 사슬(2026-09-01): 러너 프롬프트는 매니페스트가 기대하는 오퍼레이션
    // 코드를 실제로 말해야 한다. 실측 드리프트 1회 — 재도려내기 때 정답·브리핑은 C005 로 갔는데
    // 프롬프트만 옛 정답(I2570)을 요구해, 그대로 돌렸으면 기준선에 있는 것을 다시 만들었을 것이다.
    const codes = added.map((rel) => /api\/integration\.([\w-]+)\.http$/.exec(rel)?.[1]).filter((x): x is string => !!x);
    const chainOwner = taskNames.find((n) => new RegExp(`^ {2}${n}:[\\s\\S]*?reference:\\s*"${ref}"`, "m").test(tasksBlock));
    if (chainOwner !== undefined && codes.length > 0) {
      const body2 = new RegExp(`^ {2}${chainOwner}:\\s*\\{([\\s\\S]*?)^ {2}\\},`, "m").exec(tasksBlock)?.[1] ?? "";
      for (const code of codes) {
        if (!body2.includes(code)) {
          issues.push(`과제 '${chainOwner}' 의 프롬프트가 매니페스트의 오퍼레이션 코드 '${code}' 를 말하지 않는다 — 정답·브리핑·프롬프트는 한 사슬이어야 한다 (bench-tasks.md)`);
        }
      }
    }
    // expect 는 이 ref 를 쓰는 과제에 선언돼 있다.
    const owner = taskNames.find((n) => new RegExp(`^ {2}${n}:[\\s\\S]*?reference:\\s*"${ref}"`, "m").test(tasksBlock));
    if (owner !== undefined) {
      const body = new RegExp(`^ {2}${owner}:\\s*\\{([\\s\\S]*?)^ {2}\\},`, "m").exec(tasksBlock)?.[1] ?? "";
      const expect = Number(/expect:\s*(\d+)/.exec(body)?.[1] ?? NaN);
      const total = added.length + (manifest.modified ?? []).length;
      if (Number.isFinite(expect) && expect !== total) {
        issues.push(`과제 '${owner}' 의 expect(${expect}) 가 reference/${f} 의 added+modified(${total}) 와 다르다 (bench-tasks.md 4)`);
      }
    }
  }
}

// --- 3. 이름으로 부른다 ---
const NAMED = [RUNNER, join(SKILL, "SKILL.md")];
for (const dir of [join(SKILL, "tasks")]) {
  if (existsSync(dir)) for (const f of readdirSync(dir)) NAMED.push(join(dir, f));
}
for (const abs of NAMED) {
  if (!existsSync(abs)) continue;
  readFileSync(abs, "utf-8").split("\n").forEach((line, i) => {
    if (/\bMode\s+[AB]\b|\bmode:\s*"[AB]"/.test(line)) {
      issues.push(`${abs.replace(ROOT + "/", "")}:${i + 1}: 과제를 글자(Mode A/B)로 부른다 — 이름으로 부른다 (bench-tasks.md 3)`);
    }
  });
}

if (issues.length > 0) {
  console.error("check-bench-tasks: " + issues.join("\ncheck-bench-tasks: "));
  process.exit(1);
}
console.log("check-bench-tasks: OK");
