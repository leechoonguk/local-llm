/**
 * check-harness-sync — sandbox/ 와 ~/Workspace/fast-api-standard 의 수렴 상태를 기계로 판정한다.
 *
 * 규칙: .claude/rules/harness-sync.md · 절차: /harness-sync 스킬
 * 계약: 두 트리는 **의도 분기 원장(sandbox/SANDBOX.md)에 등재된 항목만 빼고 동일**하다.
 * 원장에 없는 diff 는 싱크 부채로 빨간불이다. 세 층위로 판정한다:
 *
 *  1. 피험자 코드(backend/app·tests·alembic, frontend/src, api/*.http, backend/Makefile)
 *     — 무관용 바이트 동일. 여기의 diff 는 어떤 사유로도 허용되지 않는다.
 *  2. 원장 파일 — 존재가 한쪽뿐이거나(TREE_ONLY) diff 줄 전부가 허용 패턴에 매치(PATTERN_OK)
 *     하거나 값 자체가 트리별(VALUE_OK: env·포트·compose 이름·덱 생성물).
 *  3. 루트 Makefile — 타깃 집합의 차이가 정확히 fas 전용 {commit, push} 인지.
 *
 * check-live-sync 와 같은 예외 부류다: 프로젝트 밖(fas 트리)을 읽는다. fas 가 없는
 * 호스트에서는 skip 으로 처리해 verify 를 깨지 않는다. 허용 목록을 여기 추가할 때는
 * SANDBOX.md 원장에 같은 항목의 행이 있어야 한다 — 이 검사가 그 언급을 강제한다.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { type Check, type Issue, isMain, runCli } from "./lib/harness.ts";

const ROOT = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const SB = join(ROOT, "sandbox");
const FAS = join(homedir(), "Workspace", "fast-api-standard");

/** 한쪽에만 존재해도 되는 경로(원장 사유 필수). 키는 상대 경로 prefix. */
const TREE_ONLY: Record<string, string> = {
  ".omp/hooks/pre/strict-no-vcs-publish.ts": "sandbox 정책: 피험자 VCS 전면 금지",
  ".omp/hooks/pre/strict-publish-consent.ts": "fas 정책: 동의 기반 발행",
  ".omp/hooks/pre/strict-verified-git.ts": "fas 정책: 검증된 발행",
  ".omp/hooks/lib/hook-publish-consent.ts": "fas 정책 가드의 전용 lib",
  "SANDBOX.md": "sandbox 트리 설명 + 이 원장 자신",
  "decks/package-lock.json": "덱 빌드 로컬 산물",
};

/** 값 자체가 트리별인 파일(전문 diff 허용 — 포트 대역·프로젝트명·생성물). */
const VALUE_OK = new Set([
  ".env", ".env.example", "api/.env", "api/.env.example",
  "backend/.env", "backend/.env.example", ".vscode/launch.json",
  "docker-compose.yml", "backend/.coverage",
  "decks/harness-rules/slides.md", "decks/omp-harness/slides.md",
]);

/** diff 줄 전부가 이 패턴에 매치해야 통과하는 파일 — 정책 어휘로 한정된 부분 분기. */
const PATTERN_OK: Record<string, RegExp> = {
  ".omp/RULES.md": /commit|push|publish|consent|verify|`make|서브에이전트|슬롯|GPU|문맥 비용|에이전트|병렬|^$/i, // 발행 정책 + no-subagents 사유문(정책 동일, 근거만 트리별)
  ".omp/rules/root-git-workflow.md": /./, // 파일 전체가 발행 정책이다 — sandbox 판은 VCS 금지, fas 판은 동의 기반 발행
  ".omp/rules/root-makefile.md": /commit|push|publish/i,
  ".omp/rules/omp-hooks.md": /no-vcs-publish|publish-consent|verified-git|hook-publish-consent|RULES\.md/,
  ".omp/skills/commit/SKILL.md": /./, // 발행 스킬 자체가 정책이다 — 전문 트리별
  ".omp/hooks/pre/strict-no-subagents.ts": /./, // 정책 동일, 사유문(로컬 GPU 한 슬롯)만 트리별
};

/** 루트 Makefile: 타깃 집합 차이는 정확히 fas 전용 {commit, push} 여야 한다. */
const FAS_ONLY_TARGETS = new Set(["commit", "push"]);

const EXCLUDES = [".git", "node_modules", ".venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", "dist", "state", "slides.html", ".DS_Store", ".coverage"];

export const notes: string[] = [];

export function run(_root: string): Issue[] {
  notes.length = 0;
  const issues: Issue[] = [];
  // 벤치 셀이 도는 동안 피험자 산출물은 정상적으로 sandbox 에만 있다(셀 종료 시 원복) —
  // 그 상태를 부채로 읽으면 모든 셀에서 오탐한다. 셀 중에는 판정하지 않는다(2026-09-01).
  const cell = execFileSync("bash", ["-c", "pgrep -f 'omp -p' >/dev/null && echo 1 || true"], { encoding: "utf-8" }).trim();
  if (cell === "1") { notes.push("harness-sync: 벤치 셀 실행 중 — 수렴 판정은 셀 종료 후"); return issues; }
  if (!existsSync(FAS) || !existsSync(SB)) {
    notes.push(`harness-sync: ${!existsSync(FAS) ? FAS : SB} 없음 — 건너뜀(이 호스트에는 짝 트리가 없다)`);
    return issues;
  }

  // --- 전수 diff 목록 ---
  const args = ["-rq", ...EXCLUDES.flatMap((e) => ["-x", e]), FAS, SB];
  let out = "";
  try {
    out = execFileSync("diff", args, { encoding: "utf-8", maxBuffer: 8 * 1024 * 1024 });
  } catch (e) {
    out = String((e as { stdout?: string }).stdout ?? "");
  }
  const ledger = existsSync(join(SB, "SANDBOX.md")) ? readFileSync(join(SB, "SANDBOX.md"), "utf-8") : "";

  for (const line of out.split("\n").map((l) => l.trim()).filter(Boolean)) {
    const only = /^Only in (.+): (.+)$/.exec(line);
    const differ = /^Files (.+) and (.+) differ$/.exec(line);
    const rel = only
      ? join(only[1], only[2]).replace(`${FAS}/`, "").replace(`${SB}/`, "")
      : (differ ? differ[1].replace(`${FAS}/`, "") : line);
    if (rel.startsWith(".omp/state/")) continue;

    if (only) {
      const allowed = Object.keys(TREE_ONLY).find((k) => rel === k || rel.startsWith(`${k}/`));
      if (allowed) {
        if (!ledgerMentions(ledger, allowed)) issues.push(`${rel}: 한쪽 전용은 허용이나 SANDBOX.md 원장에 언급이 없다 — 원장 행을 추가하라`);
        continue;
      }
      issues.push(`${rel}: 한쪽 트리에만 존재한다(${only[1].includes("fast-api") ? "fas" : "sandbox"} 전용) — 이식하거나 TREE_ONLY+원장에 등재하라 (/harness-sync)`);
      continue;
    }
    if (!differ) continue;

    if (rel === "Makefile") {
      issues.push(...checkRootMakefile());
      continue;
    }
    if (VALUE_OK.has(rel)) {
      if (!ledgerMentions(ledger, rel)) issues.push(`${rel}: 값 분기는 허용이나 SANDBOX.md 원장에 언급이 없다`);
      continue;
    }
    const pat = PATTERN_OK[rel];
    if (pat) {
      const bad = diffLines(join(FAS, rel), join(SB, rel)).filter((l) => !pat.test(l));
      if (bad.length > 0) {
        issues.push(`${rel}: 정책 어휘 밖의 diff ${bad.length}줄 — 첫 줄: "${bad[0].slice(0, 70)}" — 수렴하거나 원장·패턴을 넓혀라`);
      }
      continue;
    }
    issues.push(`${rel}: 원장에 없는 diff — 싱크 부채다. /harness-sync 로 수렴하거나 원장에 등재하라`);
  }
  return issues;
}

function ledgerMentions(ledger: string, rel: string): boolean {
  const base = rel.split("/").pop() ?? rel;
  return ledger.includes(rel) || ledger.includes(base) || ledger.includes(base.replace(/\.(ts|md|yml|json)$/, ""));
}

function diffLines(a: string, b: string): string[] {
  try {
    execFileSync("diff", [a, b], { encoding: "utf-8" });
    return [];
  } catch (e) {
    return String((e as { stdout?: string }).stdout ?? "")
      .split("\n")
      .filter((l) => /^[<>]/.test(l))
      .map((l) => l.slice(2).trim())
      .filter(Boolean);
  }
}

function checkRootMakefile(): Issue[] {
  const targets = (p: string): Set<string> =>
    new Set([...readFileSync(p, "utf-8").matchAll(/^([a-z][\w-]*):/gm)].map((m) => m[1]));
  const f = targets(join(FAS, "Makefile")), s = targets(join(SB, "Makefile"));
  const issues: Issue[] = [];
  for (const t of f) if (!s.has(t) && !FAS_ONLY_TARGETS.has(t)) issues.push(`Makefile: fas 에만 있는 타깃 '${t}' — 이식하거나 FAS_ONLY_TARGETS+원장에 등재하라`);
  for (const t of s) if (!f.has(t)) issues.push(`Makefile: sandbox 에만 있는 타깃 '${t}' — 이식하라(벤치 타깃이면 원장·목록에 등재)`);
  return issues;
}

export const check: Check = { name: "check-harness-sync", run };
if (isMain(import.meta.url)) runCli(check);
