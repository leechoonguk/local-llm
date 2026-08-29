/**
 * Session Discipline — zero-base redesign (2026-08-27) from measured lessons.
 *
 * Design system (every principle carries its measurement):
 *  1. Knowledge lives in docs. The rulebook checklist + Exemplar Map took the
 *     hookless REST gate to 2/2 (fixed-harness-baseline). Docs are for WHAT.
 *  2. Behavior moves only through runtime messages. Injected turn-time
 *     messages worked every time they fired (verify nudge pulled the first
 *     verification from 25+ to ~14 minutes; finish-check redirected four real
 *     finishes; red re-drives led to green recoveries). Static doc directives
 *     for tool choice or work order were adopted zero times in two campaigns
 *     and were removed. Hooks are for WHEN.
 *  3. Sickness is wall time only. Turn counts over-fire on fast turns and
 *     under-fire on slow ones (both measured); 7m stall / 12m red-age.
 *  4. Start early, guard the finish. The two green hook cells shared exactly
 *     these two levers; everything in between belongs to the model.
 *  5. Destruction is blocked, not advised (strict-* pre hooks + the verify
 *     gate). This module only nudges and cuts; it never blocks.
 *
 * Signals (all sickness- or blindness-triggered; healthy sessions pay zero):
 *  - VERIFY-NUDGE  once: mutations ran VERIFY_NUDGE_MS with no verification
 *    observed. Basis: every near-miss ran its first verification 25+ min in.
 *  - TEST-NUDGE    once: SRC_BEFORE_TESTS+ source files written, zero files
 *    under a tests/ directory, TEST_NUDGE_MS after the first mutation.
 *    Basis: every timeout died in a late test pile (53-57% coverage, NameError
 *    against 30-minute-old code); a cell was observed at minute 26 with zero
 *    test files while the doc directive for the same behavior went unadopted.
 *  - SICKNESS CUT  stall (no successful mutation for STALL_MS) or red-age
 *    (verification failing for RED_AGE_MS). Two-phase: checkpoint request with
 *    context intact, then a persistent window cut; canceled if the session
 *    recovers inside the checkpoint turn (measured: a cut once fired after
 *    green). Windows persist until superseded (measured: one-shot rewrites
 *    lasted a single call, ctx 80k->22k->81k) and are released at agent_end
 *    (measured: the injected bootstrap re-drove a finished session to the cap).
 *  - HYGIENE CUT   context grew HYGIENE_BUDGET since the last cut. Basis:
 *    without cuts ctx hit 101k and dt crawled to 308s; a cut costs ~6.5s vs
 *    omp compaction's 48.5s and recovers dt 2-4x (119.7s -> 3.5-17s).
 *  - END-GATES     a prose finish while red is re-driven (END_GATE_MAX);
 *    any mutated finish gets ONE full-verification re-drive. Basis: scope
 *    green (a passing subset cleared red while the gate failed), a finish
 *    with api/notice.http missing, and a hidden 57%-coverage fake-done were
 *    each caught live.
 *  - OPENING-BRIEF one message at the first turn: the measured recipe of the
 *    fastest green cell (spontaneous first verification at +9.2m, tests
 *    riding with their layers, 32 writes, 21.2-minute finish). Every nudge
 *    fires 10-15 minutes in — after the opening has already set the
 *    trajectory; this moves the proven message channel to minute zero.
 *  - REG-WATCH    a mutation touching a registration file (alembic/env.py,
 *    tests/conftest.py) is followed by an import-line diff against the
 *    session-start snapshot; a vanished line gets one immediate message.
 *    Basis: the single most frequent regression (a registration import
 *    removed — four occurrences) slipped past three guard vectors (edit
 *    swap, two-step remove+add, bash sed) and was only caught by verify
 *    20+ minutes later; the runtime-message channel is the one that works.
 *  - Guards: truncated pipelines (| tail/head/...) never clear red (measured
 *    fake green via `make verify | tail -30`); tool-policy blocks are not
 *    task failures.
 *
 * Knobs are fixed constants (local bench target only — the config/profile
 * layer was reverted by user decision). Logging only when STUCK_RESET_LOG set.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { resolve } from "node:path";

const FULL_GATE_RE = /\bmake\b[^|;&]*\bverify\b(?!-fast)|\bmake\b[^|;&]*\btest\b(?!-fast)/;
// 하위 디렉터리로 좁힌 게이트는 풀 게이트가 아니다. 실측 2026-08-29: 피험자가
// `cd …/sandbox/backend && make verify` 를 11회 돌리고 루트 게이트는 0회였는데 하네스가 초록으로
// 셌고, 최종 루트 게이트는 `notice: router exists but api/notice.http is missing` 로 exit 2 였다.
const SUBDIR_GATE_RE = /\bcd\s+[^\s;&|]*\/(backend|frontend|api|decks)\b|\bmake\b[^|;&]*\s-C\s+(backend|frontend|api|decks)\b/; // full-gate command shapes (verify-fast 는 full 게이트가 아니다 — 타깃 자체도 제거됨, 2026-08-28)
const HYGIENE_BUDGET = 50_000;       // session-token growth per hygiene cut
// 절대 상한(2026-08-30): 성장 기반 예산만으로는 **정체된 세션**을 못 잡는다 — 축소판 첫 셀에서
// ctx 96,074·턴 183초까지 갔는데 컷이 한 번도 안 걸렸다(증가폭이 예산에 못 미쳐서다).
// 질병 컷을 되살리지 않고 같은 구멍을 막는 최소 장치다. 창을 모르면(0) 적용하지 않는다.
// 창의 이 비율을 넘으면 성장과 무관하게 컷. 셀마다 켜고 끌 수 있게 환경변수로 뺀다(0 이면 끔) —
// 하네스를 고치지 않고 같은 조건에서 두 팔을 번갈아 돌리기 위해서다(2026-08-30 rest 분산 판정용).
const hygieneCeiling = (): number => {
  const v = Number(process.env.BENCH_HYGIENE_CEILING);
  return Number.isFinite(v) && v >= 0 && v <= 1 ? v : 0.6;
};
// 70% 는 실측에서 아슬하게 안 걸렸다(2026-08-30 두 셀: ctx 최대 82.8k·88.8k vs 131k 창의 70%=91.7k)
// — 그 사이 턴은 224초까지 늘어져 있었다. 60%(78.6k)면 두 셀 모두에서 걸렸을 자리다.
const MAX_HYGIENE = 3;
const KEEP_RECENT = 4;               // messages kept across a cut
const END_GATE_MAX = 2;              // red-finish re-drives
const SMALL_FOOTPRINT = 2;           // 프롬프트 단위 작업에서 타깃 검증으로 마감 가능한 변경 파일 수 (2026-08-28 실측: 한 줄 docstring 편집 한 건에 풀 게이트가 강제돼 104초 중 59초를 먹었다)
const FAST_GATE_RE = /\bmake\b[^|;&]*\bverify-fast\b|\bpytest\b/; // 타깃/빠른 검증 명령 모양
const REG_FILES = [ // registration/wiring files under watch — line-replacement is this model's chronic habit (7th observation: services.py User->Notice wholesale swap, 2026-08-28)
  "backend/alembic/env.py",
  "backend/tests/conftest.py",
  "backend/app/dependencies/services.py",
  "backend/app/main.py",
];
const REG_WATCH_MAX = 3;             // registration-loss messages **per watched file**(2026-08-28: 세션 상한이 앞선 파일들에서 소진돼 main.py 소실 때 침묵했다 — 회귀 1건)

export function registerDiscipline(pi: any): void {
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };

  let endGateSends = 0;
  let mutatedEver = false;
  const persisted = loadPersisted();
  let lastGateAt = persisted.lastGateAt ?? 0, lastNoticeAt = persisted.lastNoticeAt ?? 0, gateBlocks = 0, turnCount = 0;
  let lastFastGateAt = 0, lastMutationAt = 0;
  const unverified = new Set<string>();
  const srcWritten = new Set<string>();
  const testWritten = new Set<string>();
  let redSig: string | null = null;
  let redCmdTk: Set<string> | null = null;
  let phase: "idle" | "checkpoint" | "cutting" = "idle";
  let cutIndex = -1;
  let cutBootstrap: string | null = null;
  let hygieneCuts = 0;
  let lastTurnAt = Date.now();
  let tokensAtCut = 0;
  let armed = false;
  let bootstrap: string | null = null;
  const regSnapshot = new Map<string, Set<string>>();
  const regWarned = new Set<string>();
  const regWarnCount = new Map<string, number>();
  for (const rel of REG_FILES) {
    try {
      const abs = resolve(process.cwd(), rel);
      if (existsSync(abs)) regSnapshot.set(rel, importLines(readFileSync(abs, "utf-8")));
    } catch {}
  }

  function regCheck(touched: string): void {
    for (const rel of REG_FILES) {
      if (!touched.endsWith(rel) && !rel.endsWith(touched) && !touched.includes(rel.split("/").pop() ?? rel)) continue;
      const snap = regSnapshot.get(rel);
      if (!snap) continue;
      try {
        const abs = resolve(process.cwd(), rel);
        if (!existsSync(abs)) continue;
        const cur = importLines(readFileSync(abs, "utf-8"));
        const dropped = [...snap].filter((l) => !cur.has(l) && !regWarned.has(l));
        if (dropped.length === 0 || (regWarnCount.get(rel) ?? 0) >= REG_WATCH_MAX) continue;
        dropped.forEach((l) => regWarned.add(l));
        regWarnCount.set(rel, (regWarnCount.get(rel) ?? 0) + 1);
        pi.sendUserMessage(`A registration line just vanished from ${rel}: \`${dropped[0]}\`${dropped.length > 1 ? ` (+${dropped.length - 1} more)` : ""}. These imports register models/behavior the rest of the code depends on — restore the line and add yours alongside it instead of replacing.`);
        log(`REG-WATCH ${rel}: ${dropped[0].slice(0, 60)}`);
      } catch {}
    }
  }

  log(`loaded discipline. hygiene=${Math.round(HYGIENE_BUDGET / 1000)}k x${MAX_HYGIENE} endGate=${END_GATE_MAX} regWatch=${regSnapshot.size}files`);

  function beginCheckpoint(reason: string) {
        phase = "checkpoint";
    bootstrap = `[continuity] Context was cleared because ${reason}. The system prompt is unchanged, `
      + `and the todo list holds the checkpoint you just wrote — read it and continue from there.\n`
      + `Step back, reconsider the approach, and continue the remaining work a different way. `
      + `Re-run the project's verification early to confirm where things stand.`;
    // 실측 2026-08-30: 이 문구로 받은 투두는 "어디까지 했나"(11단계 계획)만 담고 있었고, 요구한 세
    // 가지 중 둘(쫓던 실패 인용·직전 시도)이 없었다. 게다가 `op:"init"` 로 목록을 통째로 다시 깔아
    // 이전 맥락을 덮었다(한 셀에서 3회). 컷 뒤 남는 것은 최근 4개 메시지와 이 투두뿐이므로,
    // 여기에 없는 것은 사라진다. 그래서 형식을 지정해 요구한다.
    pi.sendUserMessage(`[continuity] Checkpoint before a context reset (${reason}). `
      + `The context is about to be cut: after it, the only things left are the last few messages and this todo list, `
      + `so anything missing from it is gone. Rewrite the list now, carrying EVERY existing item forward with its `
      + `current state, and append these three (the tool replaces the list, so anything you leave out is deleted):\n`
      + `  1. BLOCKED: paste the current failure line verbatim (e.g. \`FAIL: …\`), or "none" if nothing is failing.\n`
      + `  2. TRIED: what you just attempted for it, in one line.\n`
      + `  3. NEXT: the single next action.\n`
      + `Then continue working.`);
    log(`CHECKPOINT requested (${reason})`);
  }

  pi.on("tool_result", (event: any, _ctx: any) => {
    try {
      const content = contentText(event.content);
      if (event.isError && isPolicyBlock(content)) return;
      const f = failSig(content);
      // 서 있는 하네스 검사 경고 추적 — backend 스코프 verify 초록 위에서 종료한
      // 실측 셀(1738s)의 가짜완료 메커니즘. finish 시점에 lastGateAt 과 비교한다.
      if (/\[check-[a-z-]+\][^]{0,60}issue/.test(content)) { lastNoticeAt = Date.now(); savePersisted({ lastNoticeAt }); }
      if (/^bash/i.test(event.toolName)) {
        const cmdStr = norm(str(event.input)).slice(0, 300);
        const cmdTk = tokens(cmdStr);
        const truncated = /\|\s*(?:tail|head|grep|sed|awk|wc)\b/.test(cmdStr);
        const fullGate = !truncated && FULL_GATE_RE.test(cmdStr) && !SUBDIR_GATE_RE.test(cmdStr);
        if (!event.isError) {
          for (const wp of shellWritePaths(cmdStr)) {
            (/(^|\/)tests?\//.test(wp) ? testWritten : srcWritten).add(wp);
            unverified.add(wp); mutatedEver = true; lastMutationAt = Date.now(); regCheck(wp);
          }
        }
        if (!truncated && !fullGate && !event.isError && FAST_GATE_RE.test(cmdStr)) lastFastGateAt = Date.now();
        // 성공한 게이트만 검증으로 센다. 실패한 게이트까지 밀면 마감 판정이 참이 되어 차단이 침묵한다
        // (2026-08-29 실측: 마지막 게이트가 빨간 채 종료, 최종 루트 게이트 exit 2).
        if (fullGate && !event.isError && !f) {
          lastGateAt = Date.now(); unverified.clear(); savePersisted({ lastGateAt });
        }
        if (f) {
          // 시그니처 교체 = 다른 실패로 전진 중 — same-signature 시계를 절반만 남기고
          // 연장한다(총상한 RED_TOTAL_MS). 실측: gatefix-a2 에서 4개 시그니처가 12분간
          // 전진 중인데 컷이 원래 시계로 발화했다(토의 2026-08-27).
          redSig = f; redCmdTk = cmdTk; log(`red: ${f.slice(0, 100)}`);
        }
        if (!event.isError && (fullGate || (!truncated && redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5))) {
          if (f) { /* red run — not a clear */ } else {
          // 전체 게이트 성공은 가장 강한 초록 증거 — Jaccard 무관 clear.
          // 실측: 성공 셀에서 stale red 가 END-GATE 2발을 소진시켰다(토의 2026-08-27).
          if (redSig) log(fullGate ? "green — red cleared (full-gate success)" : "green — red cleared (same-command success)");
          redSig = null; redCmdTk = null;
          }
        }
      }
      if (!f && !event.isError && isMutating(event.toolName)) {
        mutatedEver = true;
        const path = String(event.input?.path ?? "");
        if (path) { (/(^|\/)tests?\//.test(path) ? testWritten : srcWritten).add(path); unverified.add(path); lastMutationAt = Date.now(); regCheck(path); }
        else if (/^bash/i.test(event.toolName)) regCheck(norm(str(event.input)).slice(0, 300));
        // 스키마 무관 백스톱: 패치형 결과는 입력에 path 가 없어도 결과 텍스트에
        // [path#TAG] 로 파일명을 남긴다 — 실셀에서 입력 트리거만으로 env.py
        // 회귀를 놓친 실측(2026-08-27)이 근거.
        regCheck(content.slice(0, 500));
      }
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  pi.on("turn_end", (e: any, ctx: any) => {
    try {
      turnCount++;
      const now = Date.now();
      const used = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      log(`turn dt=${((now - lastTurnAt) / 1000).toFixed(1)}s ctx=${used}`);
      lastTurnAt = now;
      if (tokensAtCut === 0 && used > 0) tokensAtCut = used;

      if (phase === "checkpoint") {
        phase = "cutting"; armed = true;
        return;
      }
      // 런타임이 사용률을 알려주는 방식이 여러 가지다 — 예전 profile.ts 가 쓰던 키 목록을 그대로 따른다.
      // 실측 2026-08-30: `window`/`max` 만 보다가 ctx 99,993 에서도 상한이 발화하지 못했다(창 미상 처리).
      const frac = (() => {
        try {
          const u = (ctx.getContextUsage?.() ?? {}) as Record<string, unknown>;
          for (const k of ["percentage", "percent", "usedPercent"]) {
            const v = Number(u[k]);
            if (Number.isFinite(v) && v > 0) return v > 1 ? v / 100 : v;
          }
          const t = Number(u.tokens ?? u.used);
          const w = Number(u.contextWindow ?? u.window ?? u.max);
          return Number.isFinite(t) && Number.isFinite(w) && w > 0 ? t / w : 0;
        } catch { return 0; }
      })();
      const ceil = hygieneCeiling();
      const overCeiling = ceil > 0 && frac >= ceil;
      if (phase === "idle" && (overCeiling || (hygieneCuts < MAX_HYGIENE && tokensAtCut > 0 && used - tokensAtCut >= HYGIENE_BUDGET))) {
        beginCheckpoint(overCeiling
          ? `the context is at ~${Math.round(frac * 100)}% of the window (~${Math.round(used / 1000)}k tokens)`
          : `the context grew by ~${Math.round((used - tokensAtCut) / 1000)}k tokens since the last cut`);
        return;
      }
      const prose = !(e.toolResults && e.toolResults.length);
      if (phase === "idle" && prose && endGateSends < END_GATE_MAX) {
        if (redSig) {
          endGateSends++;
          pi.sendUserMessage(`You just finished your answer, but the last observed verification result was failing:\n${redSig.slice(0, 300)}\nRe-run the verification to confirm it actually passes, and finish the remaining failures if any are left.`);
          log(`END-GATE re-drive #${endGateSends}`);
        } else if (mutatedEver && (lastGateAt < lastMutationAt || (lastNoticeAt > 0 && lastNoticeAt > lastGateAt))) {
          // 하드 finish-block(무제한·멱등): 널 블록에서 full 게이트 무실행 종료와
          // backend 스코프 초록 + 서 있는 check-* 경고 위 종료가 finish-check ×2 를
          // 통과했다(2026-08-28 부검). 게이트의 완료 정의를 기계로 집행한다.
          // 비례 규칙(2026-08-28): 아직 풀 게이트가 한 번도 안 돈 세션에서 변경이 SMALL_FOOTPRINT 이하이고
          // 서 있는 check-* 경고가 없으면, 마감 조건은 풀 게이트가 아니라 타깃 검증이다. 프롬프트 단위 작업에서
          // 한 파일 편집에 40분 셀용 풀 게이트를 물리면 그 프롬프트 시간의 절반 이상이 게이트로 간다(실측 59/104초).
          // 벤치 셀은 변경이 13~15 파일이라 이 경로로 새지 않는다.
          const noticeStanding = lastNoticeAt > 0 && lastNoticeAt > lastGateAt;
          const small = !noticeStanding && unverified.size > 0 && unverified.size <= SMALL_FOOTPRINT;
          if (small && lastFastGateAt > lastMutationAt) {
            log(`FINISH-OK targeted (${unverified.size} file(s), fast gate after the last edit)`);
          } else {
            gateBlocks++;
            if (small) {
              pi.sendUserMessage(`You are finishing after changing ${unverified.size} file(s) with nothing verified since. Run the check that covers what you touched — \`make verify-fast\`, or pytest on the touched test file — and fix what it reports before finishing.`);
              log(`FINISH-BLOCK #${gateBlocks} (targeted, ${unverified.size} file)`);
            } else {
              const why = noticeStanding
                ? "a harness check notice was raised after your last full verification run"
                : "the full verification has not run since your last change";
              let bmsg = `You are finishing, but ${why}. Run \`make verify\` from the sandbox root end-to-end now, address anything it or a standing system-notice reports, and only then finish.`;
              if (gateBlocks >= 3) bmsg += ` The single next action is exactly: make verify`;
              pi.sendUserMessage(bmsg);
              log(`FINISH-BLOCK #${gateBlocks}`);
            }
          }
        }
      }
    } catch (e2) { log(`turn_end ERR ${String(e2)}`); }
  });

  pi.on("context", (event: any, ctx: any) => {
    try {
      const msgs = event.messages || [];
      if (armed) {
        armed = false;
        cutIndex = Math.max(0, msgs.length - KEEP_RECENT);
        cutBootstrap = bootstrap;
        hygieneCuts++;
        tokensAtCut = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
        phase = "idle";
        log(`RESET window @${cutIndex}/${msgs.length} (hygiene cut #${hygieneCuts})`);
      }
      if (cutIndex < 0) return undefined;
      if (cutIndex > msgs.length) { cutIndex = -1; return undefined; }
      const sys = msgs.filter((m: any) => m.role === "system");
      const bootMsg = { role: "user", content: cutBootstrap };
      const seen = new Set<any>();
      const kept = [...sys, bootMsg, ...msgs.slice(cutIndex)].filter((m) => (seen.has(m) ? false : (seen.add(m), true)));
      return { messages: kept };
    } catch (e) { log(`context ERR ${String(e)}`); return undefined; }
  });

  pi.on("agent_end", (e: any) => {
    log(`agent_end msgs=${(e.messages||[]).length} endGate=${endGateSends} red=${redSig ? "YES" : "no"} phase=${phase}`);
    cutIndex = -1; cutBootstrap = null; phase = "idle"; armed = false; bootstrap = null;
    // A released window means a revived session returns at FULL size (125k
    // measured) while the hygiene baseline still points at the cut-time value,
    // so the next hygiene cut comes far too late. Re-baseline on the next turn.
    tokensAtCut = 0;
  });
}

// ---- helpers (details after the entry point — check-code-layout) ----
function importLines(content: string): Set<string> {
  // 감시 줄 = import + DI 별칭(*Dep = Annotated[...]) + 라우터 등록(include_router).
  // import 만으로는 services.py 의 Dep 교체·main.py 의 라우터 소실을 못 본다(실측).
  return new Set(content.split("\n").map((l) => l.trim()).filter((l) =>
    /^(from\s+\S+\s+import\b|import\s+\S)/.test(l)
    || /^\w+Dep\s*=\s*Annotated\b/.test(l)
    || /\binclude_router\(/.test(l)));
}

// 프롬프트 간 상태(2026-08-29 실측): 인터랙티브에서 프롬프트 하나 = omp 프로세스 하나라
// lastGateAt·브리핑 여부가 매 프롬프트 초기화됐다. 4프롬프트 세션에서 p2·p3 이 게이트를 15회
// 돌았는데 p4 가 "이 세션은 풀 검증을 한 번도 안 돌렸다"며 다시 막았다. 벤치 러너는 셀마다
// .omp/state 를 지우므로 셀은 영향을 받지 않는다.
const STATE_DIR = ".omp/state";
const STATE_FILE = `${STATE_DIR}/discipline.json`;
type Persisted = { briefedAt?: number; lastGateAt?: number; lastNoticeAt?: number };
function loadPersisted(): Persisted {
  try { return JSON.parse(readFileSync(STATE_FILE, "utf-8")) as Persisted; } catch { return {}; }
}
function savePersisted(patch: Persisted): void {
  try {
    const cur = loadPersisted();
    const next: Persisted = {
      briefedAt: Math.max(cur.briefedAt ?? 0, patch.briefedAt ?? 0) || undefined,
      lastGateAt: Math.max(cur.lastGateAt ?? 0, patch.lastGateAt ?? 0) || undefined,
      lastNoticeAt: Math.max(cur.lastNoticeAt ?? 0, patch.lastNoticeAt ?? 0) || undefined,
    };
    mkdirSync(STATE_DIR, { recursive: true });
    writeFileSync(STATE_FILE, JSON.stringify(next));
  } catch { /* 훅·확장은 절대 던지지 않는다 */ }
}

// 셸로 만든 파일도 변경이다 — 이 모델은 edit/write 대신 `cat > path <<'EOF'` 를 쓴다(실측: 한
// 프롬프트에서 11회). 집계에서 빠지면 변경 규모 기반 신호가 전부 어긋난다.
const SHELL_WRITE_RE = /(?:>>?|\btee\b\s+(?:-a\s+)?)\s*(["']?)([\w./@-]+\.[A-Za-z0-9]+)\1/g;
function shellWritePaths(cmd: string): string[] {
  const out: string[] = [];
  for (const m of cmd.matchAll(SHELL_WRITE_RE)) {
    const q = m[2];
    if (!q || /^\/dev\//.test(q) || /^\/tmp\//.test(q)) continue;
    out.push(q.replace(/^\.\//, ""));
  }
  return out;
}
const norm = (s: string) => s.replace(/\s+/g, " ").trim();
const str = (x: any) => (typeof x === "string" ? x : (() => { try { return JSON.stringify(x); } catch { return String(x); } })());
const contentText = (c: any): string => Array.isArray(c) ? c.map((x: any) => (x && typeof x.text === "string") ? x.text : "").join("\n") : (typeof c === "string" ? c : str(c));
const tokens = (s: string) => new Set(s.toLowerCase().match(/[a-z0-9_]+/g) ?? []);
function jaccard(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let inter = 0; for (const t of a) if (b.has(t)) inter++;
  return inter / (a.size + b.size - inter);
}
function failSig(content: string): string | null {
  const fails = (content.match(/^\s*(FAIL|ERROR|FAILED|Traceback|AssertionError)[:\s].*$/gim) ?? []).map(norm).sort();
  return fails.length ? fails.join(" | ") : null;
}
function isPolicyBlock(content: string): boolean {
  return /\bBlocked\b|use the .*? tool instead|instead of (cat|head|tail|grep|ls|sed|awk)|not (allowed|permitted)|requires approval|use `?(read|edit|write|grep)`? (tool )?instead/i.test(content);
}
function isMutating(toolName: string): boolean {
  return /^(write|edit|create|apply_patch|str_replace|bash|notebook)/i.test(toolName);
}
