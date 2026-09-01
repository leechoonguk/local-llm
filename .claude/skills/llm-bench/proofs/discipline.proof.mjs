// 축소판 계약 프루프 — 남은 신호는 둘뿐이다(2026-08-30: 하이진 컷도 제거, 컨텍스트 관리는 omp 소관): REG-WATCH(배선 방어), 마감 게이트
// (가짜 완료 방어), 하이진 컷(컨텍스트 초기화). 루프 감지·질병 컷·TAIL-TRIM·WRITE-STEER·
// GATE-CADENCE·TEST-NUDGE·TRUNC-RECOVERY 의 케이스는 그 신호와 함께 삭제했다(발화 0 또는 유해 실측).
// A: red persists 12 fast turns (~1 min) with edits landing -> no checkpoint (red-age turn over-fire, gone).
// B: red aged past RED_AGE_MS (12 min) with edits landing -> checkpoint (busy-loop still caught).
// C: 3 giant thinking turns x 3 min, no mutation (9 min) -> stall checkpoint (turn-count build missed this).
// D: 10 fast turns (~2.5 min) with no mutation -> no checkpoint (stall turn over-fire, gone — measured live).
// E: red-age checkpoint requested, red clears inside the checkpoint window -> cut CANCELED (no window).
// F: truncated-pipe success (`... | tail -30`) does NOT clear red (fake-green, measured); untruncated does.
// G: after a real cut, agent_end releases the window (a finished session is not re-driven).
// 이 파일은 세션 스크래치가 아니라 레포 자산이다(2026-08-28 이관) — `make check-harness-proofs`.
// 경로는 이식성을 위해 import.meta.url 과 os.tmpdir() 로 푼다.
import { tmpdir } from "node:os";
import { rmSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const FIXROOT = join(tmpdir(), "llm-bench-proof-fixtures");
// 상태 영속화(.omp/state/discipline.json) 가 레포에 새지 않도록 프루프는 임시 트리에서 돈다.
const STATEROOT = join(tmpdir(), "llm-bench-proof-state");
(await import("node:fs")).mkdirSync(STATEROOT, { recursive: true });
process.chdir(STATEROOT);
const { registerDiscipline } = await import(pathToFileURL(REPO + "/sandbox/.omp/extensions/continuity/discipline.ts").href);

let now = 1_000_000_000_000;
Date.now = () => now;

function makePiKeepState() {
  const handlers = {};
  const sent = [];
  registerDiscipline({ on: (e, h) => { handlers[e] = h; }, sendUserMessage: (m) => sent.push(m) });
  handlers.turn_end({ toolResults: [{}] }, { getContextUsage: () => ({ tokens: 0 }) }); // 첫 턴
  return { handlers, sent };
}

function makePi() {
  // 각 케이스는 독립 세션이다 — 프롬프트 간 상태 파일을 지우고 시작한다(2026-08-29 영속화 도입).
  try { rmSync(".omp/state/discipline.json"); } catch { /* 없으면 그만 */ }
  const handlers = {};
  const sent = [];
  const pi = { on: (e, h) => { handlers[e] = h; }, sendUserMessage: (m) => sent.push(m) };
  registerDiscipline(pi);
  // 축소판에는 소비할 브리핑이 없다(RULES.md 로 이동). 첫 턴만 흘려 시계를 맞춘다.
  handlers.turn_end({ toolResults: [{}] }, { getContextUsage: () => ({ tokens: 0 }) });
  return { handlers, sent };
}
let ctxTokens = 30_000;
const ctx = { getContextUsage: () => ({ tokens: ctxTokens }) };
const bash = (h, command, text, isError = false) =>
  h.tool_result({ toolName: "bash", isError, input: { command }, content: [{ type: "text", text }] }, ctx);
const redFail = (h, command = "make verify") => bash(h, command, "FAIL: notice.py: broken thing");
const editOk = (h, path = "x.py") => h.tool_result({ toolName: "edit", isError: false, input: { path }, content: [{ type: "text", text: "ok" }] }, ctx);
const turn = (h) => h.turn_end({ toolResults: [{}] }, ctx); // tool-bearing turn: end-gate stays out of the way
const msgs = (n) => Array.from({ length: n }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: `m${i}` }));

let failures = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) failures++; };







{ // H: finishing after mutations with no verification observed -> finish-check fires
  // 기대 변경(2026-08-28): 한 파일 변경은 풀 게이트가 아니라 타깃 검증을 요구한다. 프롬프트 단위 실측에서
  // 한 줄 docstring 프롬프트가 풀 게이트 3회(321초 중 ~171초)를 먹었다 — 요구를 변경 규모에 비례시켰다.
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers);
  handlers.turn_end({}, ctx); // prose-only turn = finishing signal
  check("H: 1 file + no gate ever + prose finish -> targeted FINISH-BLOCK", sent.length === 1 && /test-fast/.test(sent[0] ?? ""));
}

{ // H2: 규모가 커지면 예전 그대로 풀 게이트를 요구한다 (벤치 셀은 13~15 파일이라 항상 이 경로)
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers, "a.py"); editOk(handlers, "b.py"); editOk(handlers, "c.py");
  handlers.turn_end({}, ctx);
  check("H2: 3 files + gate older than the change -> full-gate FINISH-BLOCK", sent.length === 1 && /has not run since your last change/.test(sent[0] ?? ""));
}

{ // H3: 작은 변경을 타깃 검증으로 덮었으면 마감은 조용하다
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers);
  now += 5_000; bash(handlers, "make -C backend verify", "3 passed");
  handlers.turn_end({}, ctx);
  check("H3: 1 file + fast gate after the edit -> finish is SILENT", sent.length === 0);
}

{ // H4: 타깃 검증이 편집보다 먼저면 덮은 게 아니다 — 다시 막는다
  const { handlers, sent } = makePi();
  bash(handlers, "make -C backend verify", "3 passed");
  now += 30_000; editOk(handlers);
  handlers.turn_end({}, ctx);
  check("H4: fast gate BEFORE the edit -> still blocked", sent.length === 1 && /test-fast/.test(sent[0] ?? ""));
}

{ // H5: 서 있는 check-* 경고가 있으면 작은 변경이라도 풀 게이트다
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers);
  bash(handlers, "make verify", "green");            // 게이트 1회 (lastGateAt 세팅)
  now += 5_000; editOk(handlers);
  bash(handlers, "cat notice", "[check-backend-naming] found 1 issue in app/x.py");
  handlers.turn_end({}, ctx);
  check("H5: standing check-* notice -> full-gate FINISH-BLOCK even for 1 file", sent.length === 1 && /harness check notice/.test(sent[0] ?? ""));
}

{ // I: scope green (red cleared by a narrow success) -> finish-check still fires, once
  const { handlers, sent } = makePi();
  redFail(handlers);
  now += 30_000; bash(handlers, "make verify", "all green"); editOk(handlers);
  handlers.turn_end({}, ctx);
  check("I1: red cleared + gate seen -> prose finish is SILENT (soft check removed)", sent.length === 0);
  handlers.turn_end({}, ctx);
  check("I2: repeat finish stays silent", sent.length === 0);
}

{ // J: finishing while red -> existing red re-drive still fires
  const { handlers, sent } = makePi();
  editOk(handlers); redFail(handlers);
  handlers.turn_end({}, ctx);
  check("J: prose finish while red -> red re-drive", sent.length === 1 && /verification result was failing/.test(sent[0] ?? ""));
}





{ // O3: a test file exists early -> no nudge
  const { handlers, sent } = makePi();
  redFail(handlers); now += 10_000; bash(handlers, "make verify", "all ok");
  editOk(handlers, "app/models/a.py"); editOk(handlers, "tests/api/test_a.py"); editOk(handlers, "app/services/b.py"); editOk(handlers, "app/routers/c.py");
  for (let i = 0; i < 16; i++) { now += 60_000; editOk(handlers, "app/models/a.py"); turn(handlers); }
  check("O3: tests present -> no test nudge", sent.length === 0);
}

{ // O4: under the source threshold -> no nudge
  const { handlers, sent } = makePi();
  redFail(handlers); now += 10_000; bash(handlers, "make verify", "all ok");
  editOk(handlers, "app/models/a.py"); editOk(handlers, "app/services/b.py");
  for (let i = 0; i < 16; i++) { now += 60_000; editOk(handlers, "app/models/a.py"); turn(handlers); }
  check("O4: 2 src files -> no test nudge", sent.length === 0);
}

{ // P: REG-WATCH — registration import loss is announced immediately
  const { mkdirSync, writeFileSync, rmSync } = await import("node:fs");
  const FIX = join(FIXROOT, "regfix");
  rmSync(FIX, { recursive: true, force: true });
  mkdirSync(FIX + "/backend/alembic", { recursive: true });
  mkdirSync(FIX + "/backend/tests", { recursive: true });
  const ENV = FIX + "/backend/alembic/env.py";
  writeFileSync(ENV, "from app.models.user import User  # noqa\nfrom app.models.batch import Batch  # noqa\nrun()\n");
  writeFileSync(FIX + "/backend/tests/conftest.py", "from app.models.batch import Batch  # noqa\n");
  process.chdir(FIX);
  const { handlers, sent } = makePi();
  // cwd stays at the fixture for the whole block — regCheck resolves against cwd
  // P1: an edit that drops the User import -> immediate message
  writeFileSync(ENV, "from app.models.batch import Batch  # noqa\nfrom app.models.notice import Notice  # noqa\nrun()\n");
  handlers.tool_result({ toolName: "edit", isError: false, input: { path: "backend/alembic/env.py" }, content: [{ type: "text", text: "ok" }] }, ctx);
  check("P1: dropped registration import -> immediate message", sent.length === 1 && /vanished from backend\/alembic\/env\.py/.test(sent[0] ?? "") && /models\.user/.test(sent[0] ?? ""));
  // P2: same loss again -> no duplicate
  handlers.tool_result({ toolName: "edit", isError: false, input: { path: "backend/alembic/env.py" }, content: [{ type: "text", text: "ok" }] }, ctx);
  check("P2: same loss not repeated", sent.length === 1);
  // P3: unrelated file edit -> silent
  handlers.tool_result({ toolName: "edit", isError: false, input: { path: "backend/app/models/notice.py" }, content: [{ type: "text", text: "ok" }] }, ctx);
  check("P3: unrelated edit silent", sent.length === 1);
  // P4: bash sed touching conftest with a dropped import -> caught via command match
  writeFileSync(FIX + "/backend/tests/conftest.py", "x = 1\n");
  handlers.tool_result({ toolName: "bash", isError: false, input: { command: "sed -i '' 'd' backend/tests/conftest.py" }, content: [{ type: "text", text: "ok" }] }, ctx);
  check("P4: bash sed loss on conftest caught", sent.length === 2 && /conftest\.py/.test(sent[1] ?? ""));
  process.chdir(REPO);
}

{ // P5: REG-WATCH content-based trigger — no input path, file named only in the result text
  const { mkdirSync, writeFileSync, rmSync } = await import("node:fs");
  const FIX = join(FIXROOT, "regfix3");
  rmSync(FIX, { recursive: true, force: true });
  mkdirSync(FIX + "/backend/alembic", { recursive: true });
  mkdirSync(FIX + "/backend/tests", { recursive: true });
  writeFileSync(FIX + "/backend/alembic/env.py", "from app.models.user import User  # noqa\nrun()\n");
  writeFileSync(FIX + "/backend/tests/conftest.py", "x = 1\n");
  process.chdir(FIX);
  const { handlers, sent } = makePi();
  writeFileSync(FIX + "/backend/alembic/env.py", "run()\n");
  handlers.tool_result({ toolName: "edit", isError: false, input: {}, content: [{ type: "text", text: "[backend/alembic/env.py#AB12] applied" }] }, ctx);
  check("P5: content-only trigger catches the loss", sent.length === 1 && /vanished/.test(sent[0] ?? ""));
  process.chdir(REPO);
}

{ // Q1: full-gate success clears red regardless of Jaccard (stale-redSig fix)
  const { handlers, sent } = makePi();
  editOk(handlers);
  redFail(handlers, ".venv/bin/pytest -q tests/core/test_seed_api_actor.py -x");
  now += 30_000; bash(handlers, "make verify", "all green, 150 passed");
  handlers.turn_end({}, ctx); // prose finish
  check("Q1: narrow red + green full gate -> finish is silent (no stale re-drive)",
    sent.length === 0);
}



{ // R1: finish-block is uncapped and releases after a real gate run
  // 규모 보정(2026-08-28): 풀 게이트 요구는 이제 SMALL_FOOTPRINT 초과에서만 걸리므로 세 파일로 세운다.
  const { handlers, sent } = makePi();
  editOk(handlers, "a.py"); editOk(handlers, "b.py"); editOk(handlers, "c.py");
  handlers.turn_end({}, ctx); handlers.turn_end({}, ctx); handlers.turn_end({}, ctx);
  check("R1a: three gate-less finishes -> three blocks, third names the command",
    sent.length === 3 && /has not run since your last change/.test(sent[2] ?? "") && /single next action/.test(sent[2] ?? ""));
  now += 10_000; bash(handlers, "make verify", "all green, 150 passed");
  handlers.turn_end({}, ctx);
  check("R1b: after a gate run the finish is silent (block released)", sent.length === 3);
}

{ // R2: a harness notice standing after the last gate run blocks the finish
  const { handlers, sent } = makePi();
  editOk(handlers);
  now += 10_000; bash(handlers, "make verify", "all green");
  now += 10_000;
  handlers.tool_result({ toolName: "edit", isError: false, input: { path: "app/models/notice.py" },
    content: [{ type: "text", text: "wrote ok <system-notice> [check-backend-domain] 3 issue(s): - notice: missing repository file" }] }, ctx);
  handlers.turn_end({}, ctx);
  check("R2a: standing check-* notice after the gate -> FINISH-BLOCK",
    sent.length === 1 && /notice was raised after your last full verification/.test(sent[0] ?? ""));
  now += 10_000; bash(handlers, "make verify", "all green again");
  handlers.turn_end({}, ctx);
  check("R2b: fresh gate after the notice -> finish is silent", sent.length === 1);
}

{ // S1: 사용자가 Esc 로 끊은 턴은 마감 신호가 아니다 (2026-08-30)
  // 중단된 턴에는 도구 결과가 없어 prose 판정이 참이 된다 — 가드가 없으면 마감 게이트가 사용자
  // 메시지를 밀어 넣어 방금 취소한 작업을 다시 굴린다(사용자에겐 Esc 가 안 먹는 것으로 보인다).
  const { handlers, sent } = makePi();
  editOk(handlers, "a.py"); editOk(handlers, "b.py"); editOk(handlers, "c.py");
  handlers.turn_end({ message: { role: "assistant", stopReason: "aborted" } }, ctx);
  check("S1a: aborted turn -> silent (Esc 가 막히지 않는다)", sent.length === 0);
  handlers.turn_end({ message: { role: "assistant", stopReason: "error" } }, ctx);
  // 오류 중단은 사용자가 멈춘 것이 아니다 — 미완인 채 조용히 끝나는 것을 막으려고 재개를 요청한다
  // (2026-09-01 실측: 벤치 셀이 18/26·게이트 빨강 상태로 32분 만에 종료, 마감 개입 0).
  check("S1b: errored turn -> RESUME 요청(사용자 중단과 구분)",
    sent.length === 1 && /runtime error/.test(sent[0] ?? ""));
  handlers.turn_end({ message: { role: "assistant", stopReason: "end_turn" } }, ctx);
  check("S1c: 정상 마감은 그대로 막힌다(가드가 게이트를 죽이지 않는다)",
    sent.length === 2 && /has not run since your last change/.test(sent[1] ?? ""));
}

{ // S2: 오류 중단의 재개 요청도 END_GATE_MAX 예산을 공유한다(무한 재구동 금지)
  const { handlers, sent } = makePi();
  editOk(handlers, "a.py"); editOk(handlers, "b.py"); editOk(handlers, "c.py");
  const err = () => handlers.turn_end({ message: { role: "assistant", stopReason: "error" } }, ctx);
  err(); err(); err();
  check("S2a: 오류 재개는 END_GATE_MAX(2) 까지만", sent.length === 2);
}

{ // S3: 아무것도 안 바꾼 세션의 오류 중단은 조용하다(할 말이 없다)
  const { handlers, sent } = makePi();
  handlers.turn_end({ message: { role: "assistant", stopReason: "error" } }, ctx);
  check("S3: 변경 없는 오류 중단 -> 침묵", sent.length === 0);
}

{ // P6: a Dep-alias replacement in services.py is announced (non-import wiring line)
  const { mkdirSync, writeFileSync, rmSync } = await import("node:fs");
  const FIX = join(FIXROOT, "regfix6");
  rmSync(FIX, { recursive: true, force: true });
  mkdirSync(FIX + "/backend/app/dependencies", { recursive: true });
  mkdirSync(FIX + "/backend/alembic", { recursive: true });
  mkdirSync(FIX + "/backend/tests", { recursive: true });
  mkdirSync(FIX + "/backend/app", { recursive: true });
  writeFileSync(FIX + "/backend/alembic/env.py", "from app.models.user import User  # noqa\n");
  writeFileSync(FIX + "/backend/tests/conftest.py", "x = 1\n");
  writeFileSync(FIX + "/backend/app/main.py", "app.include_router(user_router)\n");
  writeFileSync(FIX + "/backend/app/dependencies/services.py",
    "UserServiceDep = Annotated[UserService, Depends(get_user_service)]\n");
  process.chdir(FIX);
  const { handlers, sent } = makePi();
  writeFileSync(FIX + "/backend/app/dependencies/services.py",
    "NoticeServiceDep = Annotated[NoticeService, Depends(get_notice_service)]\n");
  handlers.tool_result({ toolName: "edit", isError: false, input: { path: "backend/app/dependencies/services.py" }, content: [{ type: "text", text: "ok" }] }, ctx);
  check("P6: Dep-alias replacement in services.py -> announced", sent.length === 1 && /vanished/.test(sent[0] ?? ""));
  process.chdir(REPO);
}

{ // R3: verify-fast green is NOT a full gate — the finish stays blocked
  // 규모 보정(2026-08-28): 작은 변경(<=SMALL_FOOTPRINT)은 타깃 검증으로 마감할 수 있다(H3).
  // 이 케이스의 계약은 "규모가 큰 변경에서는 백엔드 게이트가 풀 게이트를 대신하지 못한다" 이다.
  const { handlers, sent } = makePi();
  editOk(handlers, "a.py"); editOk(handlers, "b.py"); editOk(handlers, "c.py");
  now += 10_000; bash(handlers, "make -C backend verify", "all green");
  handlers.turn_end({}, ctx);
  check("R3: verify-fast green + prose finish -> FINISH-BLOCK stands",
    sent.length === 1 && /has not run since your last change/.test(sent[0] ?? ""));
}





{ // X: 프롬프트 간 상태 — 인터랙티브에서 프롬프트 하나 = omp 프로세스 하나다.
  // 실측(2026-08-29 4프롬프트 세션): 브리핑이 4회 반복됐고, p2·p3 가 게이트를 15회 돌았는데
  // p4 가 "이 세션은 풀 검증을 한 번도 안 돌렸다"며 다시 막았다.
  const p1 = makePi();                                    // 프롬프트 1 (상태 초기화)
  now += 30_000; editOk(p1.handlers, "a.py");
  bash(p1.handlers, "make verify", "all green");           // 게이트 통과
  p1.handlers.turn_end({}, ctx);
  check("X1: gate after the change -> finish is silent", p1.sent.length === 0);

  const p2 = makePiKeepState();                            // 프롬프트 2 (같은 트리, 새 프로세스)
  check("X2: the brief is not repeated in the next prompt", p2.sent.length === 0);
  p2.handlers.turn_end({}, ctx);
  check("X3: carried gate + no new change -> no finish block", p2.sent.length === 0);

  now += 30_000; editOk(p2.handlers, "b.py");              // 새 변경
  p2.handlers.turn_end({}, ctx);
  check("X4: a change after the carried gate -> blocked again",
    p2.sent.length === 1 && /test-fast/.test(p2.sent[0] ?? ""));
}


{ // N: 축소판의 계약(2026-08-29). 남은 신호는 셋뿐이고, 건강한 세션은 아무 말도 듣지 않는다.
  { const handlers = {}; const sent = []; const steers = [];
    try { rmSync(".omp/state/discipline.json"); } catch { /* 없으면 그만 */ }
    registerDiscipline({
      on: (e, h) => { handlers[e] = h; },
      sendUserMessage: (m) => sent.push(m),
      // steer 채널을 쓰면 실패한다 — 이 채널이 도구 호출 2,266건을 취소했다(코퍼스 부검).
      sendMessage: (...a) => { steers.push(a); },
    });
    now += 10_000; handlers.turn_end({ toolResults: [{}] }, ctx);
    check("N1: registering the extension sends nothing (no opening brief)", sent.length === 0);
    check("N2: the steer channel is never used", steers.length === 0);

    now += 30_000;
    for (let i = 0; i < 6; i++) editOk(handlers, `app/f${i}.py`);
    bash(handlers, "make verify", "all green, 150 passed");
    handlers.turn_end({}, ctx);
    check("N3: a healthy cell — six writes, a green root gate, a prose finish — receives zero messages",
      sent.length === 0 && steers.length === 0); }

}






{ // OMP: 컨텍스트 관리는 omp 소관이다 — 확장은 문맥을 만지지 않는다(2026-08-30 짝 비교 결론).
  // ON(상한 0.6) 3셀은 자체 종료 0/3·게이트 초록 0/3, OFF(상한 0) 3셀은 1/3·1/3 이었고 회귀는 6셀 모두 0.
  // 컷이 필요하다는 근거가 하나도 없었다. 원래 근거(ctx 45k→22k)는 개입이 도구 호출을 취소하며
  // 컨텍스트를 부풀리던 옛 하네스의 수치였다.
  const handlers = {}; const sent = [];
  try { rmSync(".omp/state/discipline.json"); } catch { /* 없으면 그만 */ }
  registerDiscipline({ on: (e, h) => { handlers[e] = h; }, sendUserMessage: (m) => sent.push(m) });
  check("OMP1: the extension registers no context handler", handlers.context === undefined);
  const usage = { getContextUsage: () => ({ tokens: 125_000, contextWindow: 131_072 }) };
  handlers.turn_end({ toolResults: [{}] }, usage);
  now += 5_000; editOk(handlers, "app/x.py");
  now += 30_000; handlers.turn_end({ toolResults: [{}] }, usage);
  check("OMP2: a nearly full window produces no message", sent.length === 0);
}

process.exit(failures ? 1 : 0);
