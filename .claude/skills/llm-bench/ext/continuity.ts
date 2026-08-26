/**
 * continuity — omp 확장: 로컬 코더 연속성 하네스. (stuck-reset v1~v3 실험의 체계화, 2026-08-26)
 *
 * 원칙
 *  - **도메인 하드코딩·처방 금지.** 무엇을 어떻게 고칠지는 모델 자율. 확장은 제네릭 신호의 관측과
 *    컨텍스트 위생만 담당한다(로컬 LLM 의 자율 작업 능력을 재는 하네스이기도 하다).
 *  - **컨텍스트는 루프 안에서 적절히 초기화한다.** 진행 상태의 지속 기억은 omp 네이티브 todo
 *    (리셋 생존, 실측)이고, 리셋 부트스트랩은 모델에게 **먼저 todo 를 갱신**하라고 지시한다
 *    (훅의 직접 todo 기록은 불가 — ctx.invokeTool 부재 실측).
 *
 * 구조: 관측(observe) → 판정(decide) → 행동(act)
 *  [관측] 제네릭 신호 4개
 *    R. verify red/green — bash 결과의 실패줄(FAIL/ERROR…)로 red 기록, 실패줄 없는 bash 성공이면 해제.
 *    S. 유사 반복 — 변이 툴콜(write/edit/patch/bash; read류 탐색은 연속 파일읽기 오발 때문에 제외)과
 *       실패 결과에 토큰 자카드 유사도. 3×완전동일 감지는 이 모델(3.6)에 무용(변형 헤맴, 실측).
 *    T. 정체 — 성공한 변이 결과가 STALL_TURNS 턴 동안 0(진행 중에는 절대 안 끊는다).
 *    C. 컨텍스트 비대 — 직전 리셋 이후 토큰 증가가 CONTEXT_BUDGET 초과(위생 리셋; 맹목 주기의 일반형).
 *  [판정] 임계 상수(아래) + 안전장치 — 총 MAX_RESETS, 같은 계열 신호 지속 시 GIVE UP(강제하지 않음),
 *    툴 사용/정책 블록("cat 대신 read"류)은 과제 실패가 아니므로 제외.
 *  [행동]
 *    - 리셋: context 이벤트에서 messages → [시스템 + 부트스트랩 + 최근 KEEP_RECENT] 재작성(실측 확정.
 *      ctx.compact() 는 작은 세션에서 거부됨). 부트스트랩 = 중립: 이유·관측 사실·todo 갱신 지시.
 *    - end-gate: red 인 채 프로즈-온리 턴(끝내려는 신호)이면 turn_end 시점 pi.sendUserMessage 로
 *      1회 재구동(상한 END_GATE_MAX). agent_end 시점은 teardown 레이스로 무효(실측).
 *
 * 주의(실측 버그): tool_result content 는 [{type:"text",text}] 구조 — contentText 로 추출해야
 * 실패줄 정규식이 맞는다. 로그는 STUCK_RESET_LOG(테스트용) 경로 지정 시에만 쓴다.
 */
import { appendFileSync } from "node:fs";

// ---- 판정 임계(전부 제네릭·실측 기반; 값 튜닝은 벤치로) --------------------------------
const SIM_THRESHOLD = 0.7;      // 자카드 유사도 임계
const SIM_REPEAT = 3;           // 유사 신호 연속 N회 → thrash 리셋
const STALL_TURNS = 10;         // 성공 변이 0 인 N턴 → 정체 리셋
const CONTEXT_BUDGET = 50_000;  // 직전 리셋 이후 토큰 증가 상한 → 위생 리셋
const MAX_RESETS = 6;           // 총 리셋 상한(위생 포함이라 v3 의 4보다 여유)
const GIVEUP_AFTER = 2;         // 같은 계열 신호가 리셋 N회 후에도 지속 → 강제하지 않고 멈춤
const KEEP_RECENT = 4;          // 리셋 시 유지할 최근 메시지 수
const END_GATE_MAX = 2;         // red 종료 재구동 상한

// ---- 유틸 ------------------------------------------------------------------------
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

export default function continuity(pi: any) {
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };

  // ---- 상태 ----
  const sim: Record<string, { last: Set<string> | null; count: number }> = { mut: { last: null, count: 0 }, fail: { last: null, count: 0 } };
  const observed: string[] = [];       // task-scoped 중립 관측(부트스트랩 재주입, 프로세스 종료 시 소멸)
  let resets = 0, sigResetCount = 0, stallTurns = 0, endGateSends = 0;
  let redSig: string | null = null;
  let redCmdTk: Set<string> | null = null;  // red 를 만든 명령의 토큰(유사 명령 성공시만 해제)
  let tokensAtReset = 0;               // 위생 리셋 기준점
  let armed = false;
  let bootstrap: string | null = null;

  log(`loaded. sim>=${SIM_THRESHOLD}x${SIM_REPEAT} stall=${STALL_TURNS} budget=${CONTEXT_BUDGET} maxResets=${MAX_RESETS} endGate=${END_GATE_MAX}`);

  // ---- 행동: 리셋 무장(중립 부트스트랩 구성 — todo 갱신 지시 포함) ----
  function arm(reason: string, note: string | null) {
    if (note && !observed.includes(note)) observed.push(note);
    if (resets >= MAX_RESETS) { log(`MAX_RESETS — no reset (${reason})`); return; }
    const obs = observed.length ? `\n지금까지 반복 관측된 것(같은 것을 다시 하지 말 것):\n- ${observed.join("\n- ")}\n` : "";
    bootstrap = `[continuity] ${reason} 컨텍스트를 초기화했다. 시스템 프롬프트는 그대로다.\n`
      + `이어가기 전에 **먼저 todo 를 갱신하라** — 완료한 것, 남은 것, 방금 상태를 반영할 것. todo 가 이 작업의 기억이다.\n`
      + `그 다음 한 걸음 물러나 접근을 재검토하고, 다른 방법으로 남은 것을 이어가라. 필요하면 검증을 다시 실행하라.${obs}`;
    armed = true; resets++;
    log(`ARMED reset #${resets} (${reason})`);
  }

  // ---- 관측 S: 유사 반복 ----
  function simObserve(kind: "mut" | "fail", signal: string) {
    const st = sim[kind];
    const tk = tokens(signal);
    const s = st.last ? jaccard(tk, st.last) : 0;
    if (s >= SIM_THRESHOLD) st.count++; else st.count = 1;
    st.last = tk;
    if (st.count < SIM_REPEAT) return;
    st.count = 1;
    if (sigResetCount >= GIVEUP_AFTER) { log(`GIVE UP: similar ${kind} persists after ${sigResetCount} resets.`); return; }
    sigResetCount++;
    arm(`유사한 ${kind === "mut" ? "변경 작업" : "실패"}이 ${SIM_REPEAT}회 이상 이어져`, `${kind}~: ${signal.slice(0, 150)}`);
  }

  pi.on("tool_call", (event: any, _ctx: any) => {
    try { if (isMutating(event.toolName)) simObserve("mut", `${event.toolName} ${norm(str(event.input)).slice(0, 300)}`); }
    catch (e) { log(`tool_call ERR ${String(e)}`); }
  });

  // ---- 관측 R(red/green) + S(실패 유사) + T(진전) ----
  pi.on("tool_result", (event: any, _ctx: any) => {
    try {
      const content = contentText(event.content);
      if (event.isError && isPolicyBlock(content)) return;
      const f = failSig(content);
      if (/^bash/i.test(event.toolName)) {
        const cmdTk = tokens(norm(str(event.input)).slice(0, 300));
        if (f) { redSig = f; redCmdTk = cmdTk; log(`red: ${f.slice(0, 100)}`); }
        else if (!event.isError) {
          // red 는 **그 red 를 만든 명령과 유사한 명령**이 성공했을 때만 해제한다(자카드).
          // 아무 bash(ls 등) 성공으로 해제하면 end-gate 가 무력화된다 — 셀 실측 버그(coverage red 가
          // 무관한 bash 성공에 지워져 미완성 2 로 끝났는데 END-GATE 침묵).
          if (redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5) {
            log("green — red cleared (same-command success)"); redSig = null; redCmdTk = null; sigResetCount = 0;
          }
        }
      }
      if (f || event.isError) simObserve("fail", `${event.toolName} ${(f ?? norm(content)).slice(0, 250)}`);
      else if (isMutating(event.toolName)) stallTurns = 0;   // 성공 변이 = 진전
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  // ---- 관측 T(정체) + C(컨텍스트 비대) + 행동 end-gate ----
  pi.on("turn_end", (e: any, ctx: any) => {
    try {
      stallTurns++;
      if (!armed && stallTurns >= STALL_TURNS && resets < MAX_RESETS) {
        stallTurns = 0;
        arm(`${STALL_TURNS}턴 동안 진전(성공한 변경)이 없어`, null);
      }
      // 위생 리셋: 직전 리셋 이후 컨텍스트가 예산을 넘게 자랐으면 정리(진행과 무관한 순수 위생)
      const used = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      if (!armed && used - tokensAtReset > CONTEXT_BUDGET && resets < MAX_RESETS) {
        arm(`컨텍스트가 커져(위생)`, null);
      }
      // end-gate: red 인 채 프로즈-온리 턴 → 재구동(turn_end 에서만 유효 — 실측)
      const prose = !(e.toolResults && e.toolResults.length);
      if (prose && redSig && endGateSends < END_GATE_MAX) {
        endGateSends++;
        pi.sendUserMessage(`방금 답을 마쳤지만, 마지막으로 관측된 검증 결과가 실패 상태였다:\n${redSig.slice(0, 300)}\n검증을 다시 실행해 실제로 통과하는지 확인하고, 실패가 남아 있으면 마무리하라.`);
        log(`END-GATE re-drive #${endGateSends}`);
      }
    } catch (e2) { log(`turn_end ERR ${String(e2)}`); }
  });

  // ---- 행동: 리셋 실행(context 재작성) ----
  pi.on("context", (event: any, ctx: any) => {
    if (!armed) return undefined;
    armed = false;
    try {
      const msgs = event.messages || [];
      const sys = msgs.filter((m: any) => m.role === "system");
      const recent = msgs.slice(-KEEP_RECENT);
      const bootMsg = { role: "user", content: bootstrap };
      const seen = new Set<any>();
      const kept = [...sys, bootMsg, ...recent].filter((m) => (seen.has(m) ? false : (seen.add(m), true)));
      tokensAtReset = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      log(`RESET context ${msgs.length} -> ${kept.length}`);
      return { messages: kept };
    } catch (e) { log(`context ERR ${String(e)}`); return undefined; }
  });

  pi.on("agent_end", (e: any) => log(`agent_end msgs=${(e.messages||[]).length} resets=${resets} endGate=${endGateSends} red=${redSig ? "YES" : "no"}`));
}
