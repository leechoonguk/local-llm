#!/usr/bin/env node
/**
 * sandbox 하네스 수정 절차 검사 — `make check-sandbox-harness-edit`.
 *
 * 규칙 본문은 `.claude/rules/sandbox-harness-edit.md`. 여기서는 넷을 본다.
 *
 *  1. 셀이 도는 중에 `sandbox/.omp` 가 더럽지 않은가 — 그 셀은 두 하네스의 혼합이라 무효다.
 *  2. 피험자 트리(`sandbox/backend`·`sandbox/api`)가 스테이징돼 있지 않은가 — `git add -A` 사고의 지문이다.
 *  3. 히스토리에서 하네스와 피험자 트리가 한 커밋에 섞인 적이 없는가(최근 40커밋).
 *  4. `sandbox/.omp` 의 신호·가드 파일이 미커밋인 채로 러너가 돌 준비가 돼 있지 않은가(1 과 짝).
 *
 * git 과 프로세스를 읽는다 — 순수 파일 읽기 검사가 아니다. `check-live-sync` 와 같은 예외 부류이고,
 * git 이 없거나 sandbox 가 없는 호스트에서는 skip 한다.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const SANDBOX = join(ROOT, "sandbox");

function sh(cmd: string, args: string[]): string {
  try {
    return execFileSync(cmd, args, { cwd: ROOT, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return "";
  }
}

if (!existsSync(SANDBOX) || sh("git", ["rev-parse", "--git-dir"]).trim() === "") {
  console.log("check-sandbox-harness-edit: skip — sandbox/ 또는 git 저장소 없음");
  process.exit(0);
}

const issues: string[] = [];

// 1·4. 셀 실행 중 + 하네스 미커밋
const cellRunning = sh("pgrep", ["-f", "omp -p"]).trim() !== "";
// 러너 자신이 셀 동안 주입하는 것은 편집이 아니다(채점 전 원복됨): config.yml 의
// "# bench-advisor" 블록. 이것까지 잡으면 모든 정상 셀에서 오탐한다(2026-09-01 실측).
const dirtyFiles = sh("git", ["status", "--porcelain", "--", "sandbox/.omp"]).trim()
  .split("\n").filter(Boolean)
  .filter((l) => {
    if (!l.includes("sandbox/.omp/config.yml")) return true;
    const d = sh("git", ["diff", "--", "sandbox/.omp/config.yml"]);
    const added = d.split("\n").filter((x) => /^\+[^+]/.test(x)).map((x) => x.slice(1));
    return !(added.length > 0 && added.every((x) => /bench-advisor|advisor:|enabled: false|modelRoles:|  advisor: |immuneTurns|syncBacklog|^\s*$/.test(x)));
  });
const harnessDirty = dirtyFiles.join("\n");
if (cellRunning && harnessDirty !== "") {
  issues.push(
    "벤치 셀이 실행 중인데 sandbox/.omp 에 미커밋 변경이 있다 — 그 셀은 두 하네스의 혼합이라 무효다. " +
      `셀을 멈추거나 변경을 되돌린 뒤 진행한다:\n${harnessDirty}`,
  );
}

// 2. 하네스와 피험자 트리가 **같은 커밋에** 스테이징돼 있는가.
// 피험자 트리 단독 변경은 정상 작업이다(기준선 조정 등) — 문제는 섞이는 것이다.
// 하네스 = sandbox/.omp 만이 아니다 — d1741c4 사고는 .claude 변경과 피험자 산출물의 혼합이었다
// (2026-09-01). 피험자 쪽도 frontend 를 포함한다(풀스택 과제).
const stagedSubject = sh("git", ["diff", "--cached", "--name-only", "--", "sandbox/backend", "sandbox/api", "sandbox/frontend/src"]).trim();
const stagedHarness = sh("git", ["diff", "--cached", "--name-only", "--", "sandbox/.omp", ".claude"]).trim();
const staged = stagedSubject !== "" && stagedHarness !== "" ? stagedSubject : "";
if (staged !== "") {
  issues.push(
    "하네스와 피험자 트리가 한 커밋에 함께 스테이징됐다 — 과제 산출물이 섞이면 이후 셀이 '절반 끝난 트리'에서 시작한다. " +
      `경로를 좁혀 담는다(git add sandbox/.omp sandbox/decks):\n${staged}`,
  );
}

// 3. 히스토리에 섞인 커밋
const log = sh("git", ["log", "--format=%H %s", "-n", "40", "--", "sandbox"]).trim();
for (const line of log === "" ? [] : log.split("\n")) {
  const [hash, ...rest] = line.split(" ");
  const files = sh("git", ["show", "--pretty=", "--name-only", hash]).split("\n").map((l) => l.trim()).filter(Boolean);
  const touchesHarness = files.some((f) => f.startsWith("sandbox/.omp/"));
  // 하네스 커밋이 피험자 트리를 건드리는 것 자체는 정당할 수 있다(빠진 make 타깃 추가, `api/.env.example`).
  // 사고의 지문은 **진행 중이던 과제 산출물이 새로 추가된 것**이다 — 도메인 계층·테스트·마이그레이션.
  const added = sh("git", ["show", "--pretty=", "--name-only", "--diff-filter=A", hash])
    .split("\n").map((l) => l.trim()).filter(Boolean);
  // 위험의 실체는 도메인 경로 일반이 아니라 **현재 벤치 과제의 정답이 트리에 남는 것**이다
  // (2026-09-01 정밀화). 기준선 채택 커밋(fas 소스 통째 이식)은 마이그레이션 수십 개를 정당하게
  // 더한다 — 경로 휴리스틱은 그걸 사고로 읽었다. 사고였던 notice 커밋은 그때의 과제 정답을
  // 담았었다: 판정은 reference/*.manifest.json 의 added 목록과의 교집합으로 한다.
  const artifactAdded = added.filter((f) => taskAnswers().has(f.replace(/^sandbox\//, "")));
  // 이미 지나간 커밋을 영구히 빨갛게 두지 않는다 — 문제는 커밋 자체가 아니라 **그 산출물이
  // 기준선(HEAD)에 남아 있는 것**이다. 워크트리 존재로 판정하면 도는 셀의 정상 산출물(같은
  // 경로!)을 사고 잔재로 오독한다(2026-09-01 실측: 되돌림 커밋 후에도 셀 파일 때문에 빨강).
  const inHead = new Set(sh("git", ["ls-tree", "-r", "--name-only", "HEAD", "--", "sandbox"]).split("\n"));
  const stillPresent = artifactAdded.filter((f) => inHead.has(f));
  if (touchesHarness && stillPresent.length > 0) {
    issues.push(
      `커밋 ${hash.slice(0, 7)} 이 하네스 수정과 함께 진행 중이던 과제 산출물을 새로 담았다 — "${rest.join(" ").slice(0, 50)}" (${stillPresent.slice(0, 3).join(", ")}${stillPresent.length > 3 ? " 외" : ""}). ` +
        "그 파일들이 아직 트리에 있다 — 이대로 셀을 띄우면 과제가 절반 끝난 상태에서 시작한다. 지우고 커밋한다.",
    );
  }
}

if (issues.length > 0) {
  console.error("check-sandbox-harness-edit: " + issues.join("\ncheck-sandbox-harness-edit: "));
  process.exit(1);
}
console.log("check-sandbox-harness-edit: OK");

/** 현재 벤치 과제들의 기대 산출물(정답) 경로 — reference/*.manifest.json 의 added 합집합. */
function taskAnswers(): Set<string> {
  const out = new Set<string>();
  const dir = join(ROOT, ".claude", "skills", "llm-bench", "reference");
  try {
    for (const f of readdirSync(dir)) {
      if (!f.endsWith(".manifest.json")) continue;
      try {
        const m = JSON.parse(readFileSync(join(dir, f), "utf-8")) as { added?: string[] };
        for (const rel of m.added ?? []) out.add(rel);
      } catch { /* 깨진 매니페스트는 check-bench-tasks 소관 */ }
    }
  } catch { /* reference 없음 */ }
  return out;
}
