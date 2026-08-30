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
import { existsSync } from "node:fs";
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
const harnessDirty = sh("git", ["status", "--porcelain", "--", "sandbox/.omp"]).trim();
if (cellRunning && harnessDirty !== "") {
  issues.push(
    "벤치 셀이 실행 중인데 sandbox/.omp 에 미커밋 변경이 있다 — 그 셀은 두 하네스의 혼합이라 무효다. " +
      `셀을 멈추거나 변경을 되돌린 뒤 진행한다:\n${harnessDirty}`,
  );
}

// 2. 피험자 트리 스테이징
const staged = sh("git", ["diff", "--cached", "--name-only", "--", "sandbox/backend", "sandbox/api"]).trim();
if (staged !== "") {
  issues.push(
    "피험자 트리가 스테이징돼 있다 — 하네스 커밋에 과제 산출물이 섞이면 이후 셀이 '절반 끝난 트리'에서 시작한다. " +
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
  const artifactAdded = added.filter((f) =>
    /^sandbox\/backend\/app\/(models|schemas|repositories|services|routers)\//.test(f) ||
    f.startsWith("sandbox/backend/tests/") ||
    f.startsWith("sandbox/backend/alembic/versions/"));
  // 이미 지나간 커밋을 영구히 빨갛게 두지 않는다 — 문제는 커밋 자체가 아니라 **그 산출물이 지금도
  // 트리에 남아 있는 것**이다(그 상태에서 셀을 띄우면 과제가 절반 끝나 있다). 남아 있을 때만 막는다.
  const stillPresent = artifactAdded.filter((f) => existsSync(join(ROOT, f)));
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
