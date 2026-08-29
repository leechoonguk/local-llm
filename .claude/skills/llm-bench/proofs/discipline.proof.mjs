// Edge proof for the time-only sickness build + the three cut/finish fixes (synthetic events, no GPU).
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
  handlers.turn_end({ toolResults: [{}] }, { getContextUsage: () => ({ tokens: 0 }) }); // 첫 턴 — 브리핑이 다시 나오면 여기서 잡힌다
  return { handlers, sent };
}

function makePi() {
  // 각 케이스는 독립 세션이다 — 프롬프트 간 상태 파일을 지우고 시작한다(2026-08-29 영속화 도입).
  try { rmSync(".omp/state/discipline.json"); } catch { /* 없으면 그만 */ }
  const handlers = {};
  const sent = [];
  const pi = { on: (e, h) => { handlers[e] = h; }, sendUserMessage: (m) => sent.push(m) };
  registerDiscipline(pi);
  // consume the OPENING-BRIEF (fires on the first turn of every session)
  handlers.turn_end({ toolResults: [{}] }, { getContextUsage: () => ({ tokens: 0 }) });
  sent.length = 0;
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

{ // A + B share one instance (A is the prefix of B)
  const { handlers, sent } = makePi();
  redFail(handlers);
  for (let i = 0; i < 12; i++) { now += 5_000; editOk(handlers); turn(handlers); }
  check("A: 12 fast red turns (1 min) -> no checkpoint", sent.length === 0);
  let fired = false;
  for (let i = 0; i < 20; i++) { now += 60_000; editOk(handlers); turn(handlers); if (sent.length > 0) { fired = true; break; } }
  check("B: red aged past 12 min -> checkpoint fired", fired && /stayed failing/.test(sent[0] ?? ""));
}

{ // C: slow thinking turns, no mutation at all
  const { handlers, sent } = makePi();
  for (let i = 0; i < 3; i++) { now += 180_000; turn(handlers); }
  check("C: 3 x 3-min turns without mutation (9 min) -> stall checkpoint", sent.length === 1 && /minutes .*no successful change/.test(sent[0] ?? ""));
}

{ // D: fast read/plan stretch, no mutation, under the time threshold
  const { handlers, sent } = makePi();
  for (let i = 0; i < 10; i++) { now += 15_000; turn(handlers); }
  check("D: 10 fast turns without mutation (2.5 min) -> no checkpoint", sent.length === 0);
}

{ // E: sickness resolves inside the checkpoint window -> cancel, no cut
  const { handlers, sent } = makePi();
  redFail(handlers);
  let fired = false;
  for (let i = 0; i < 20 && !fired; i++) { now += 60_000; editOk(handlers); turn(handlers); fired = sent.length > 0; }
  check("E-pre: red-age checkpoint requested", fired);
  now += 10_000; bash(handlers, "make verify", "all green, no failures"); // red clears in the window
  editOk(handlers); turn(handlers);                                        // the would-be arming turn
  const out = handlers.context({ messages: msgs(30) }, ctx);
  check("E: cut canceled after recovery -> context untouched", out === undefined && sent.length === 1);
}

{ // F: truncated pipe never clears red; an untruncated same-command run does
  const { handlers, sent } = makePi();
  redFail(handlers, "make verify 2>&1 | tail -30");
  now += 60_000; bash(handlers, "make verify 2>&1 | tail -30", "========== 34 passed =========="); // fake green
  let fired = false;
  for (let i = 0; i < 20 && !fired; i++) { now += 60_000; editOk(handlers); turn(handlers); fired = sent.length > 0; }
  check("F1: truncated success did not clear red -> red-age still fired", fired);
  now += 10_000; bash(handlers, "make verify 2>&1", "all green");           // untruncated: clears
  editOk(handlers); turn(handlers);                                          // checkpoint window -> cancel
  const out = handlers.context({ messages: msgs(30) }, ctx);
  check("F2: untruncated same-command success cleared red -> cut canceled", out === undefined && sent.length === 1);
}

{ // G: a real cut, then agent_end releases the window
  const { handlers, sent } = makePi();
  now += 8 * 60_000; turn(handlers);                       // stall (8 min, no mutation) -> checkpoint
  check("G-pre: stall checkpoint requested", sent.length === 1);
  now += 10_000; turn(handlers);                           // still stalled -> arms the cut
  const cut = handlers.context({ messages: msgs(30) }, ctx);
  check("G-pre: cut window applied", !!cut && Array.isArray(cut.messages) && cut.messages.length < 30);
  const again = handlers.context({ messages: msgs(32) }, ctx);
  check("G-pre: window persists on the next call", !!again && Array.isArray(again.messages));
  handlers.agent_end({ messages: msgs(32) });
  const released = handlers.context({ messages: msgs(32) }, ctx);
  check("G: agent_end releases the window", released === undefined);
}

{ // H: finishing after mutations with no verification observed -> finish-check fires
  // 기대 변경(2026-08-28): 한 파일 변경은 풀 게이트가 아니라 타깃 검증을 요구한다. 프롬프트 단위 실측에서
  // 한 줄 docstring 프롬프트가 풀 게이트 3회(321초 중 ~171초)를 먹었다 — 요구를 변경 규모에 비례시켰다.
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers);
  handlers.turn_end({}, ctx); // prose-only turn = finishing signal
  // 계약 변경(2026-08-29): 인터랙티브에서 고장 없는 조각의 마감은 침묵이다.
  check("H: 1 file + no gate ever + prose finish -> silent (slice finish)", sent.length === 0);
  process.env.BENCH_CELL = "1";
  { const cell = makePi();
    now += 30_000; editOk(cell.handlers);
    cell.handlers.turn_end({}, ctx);
    check("H-cell: the same session inside a bench cell is still blocked",
      cell.sent.length === 1 && /has not run since your last change/.test(cell.sent[0] ?? "")); }
  delete process.env.BENCH_CELL;
}

{ // H2: 규모가 커지면 예전 그대로 풀 게이트를 요구한다 (벤치 셀은 13~15 파일이라 항상 이 경로)
  // 경계 보정(2026-08-29 임계 통일): 조각 = 미검증 1~6파일. 풀 게이트 요구는 7파일부터다.
  const { handlers, sent } = makePi();
  now += 30_000; for (const f of ["a","b","c","d","e","f","g"]) editOk(handlers, `${f}.py`);
  turn(handlers); sent.length = 0; // 7파일이면 게이트 케이던스가 먼저 1회 나간다 — 소비하고 마감을 본다
  handlers.turn_end({}, ctx);
  check("H2: 7 files + gate older than the change -> full-gate FINISH-BLOCK", sent.length === 1 && /has not run since your last change/.test(sent[0] ?? ""));
}

{ // H3: 작은 변경을 타깃 검증으로 덮었으면 마감은 조용하다
  const { handlers, sent } = makePi();
  now += 30_000; editOk(handlers);
  now += 5_000; bash(handlers, "make verify-fast", "3 passed");
  handlers.turn_end({}, ctx);
  check("H3: 1 file + fast gate after the edit -> finish is SILENT", sent.length === 0);
}

{ // H4: 타깃 검증이 편집보다 먼저면 덮은 게 아니다 — 다시 막는다
  const { handlers, sent } = makePi();
  bash(handlers, "make verify-fast", "3 passed");
  now += 30_000; editOk(handlers);
  handlers.turn_end({}, ctx);
  // 조각이면 타깃 검증의 선후는 마감을 좌우하지 않는다(침묵). 셀에서는 여전히 막힌다(H-cell).
  check("H4: fast gate BEFORE the edit -> slice finish is still silent", sent.length === 0);
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

{ // K: 6 distinct unverified files -> cadence nudge; 12 + 3 turns -> one escalation
  const { handlers, sent } = makePi();
  // 경계 보정(2026-08-29 임계 통일): 조각 = 미검증 1~6파일, 7부터 기능 전체.
  for (let i = 0; i < 7; i++) { now += 30_000; editOk(handlers, `app/f${i}.py`); turn(handlers); }
  check("K1: 7 distinct unverified files -> cadence nudge", sent.length === 1 && /files have changed since the last full verification/.test(sent[0] ?? ""));
  for (let i = 7; i < 13; i++) { now += 30_000; editOk(handlers, `app/f${i}.py`); turn(handlers); }
  check("K2: 13 unverified + 3 turns -> one escalation, once", sent.length === 2 && /Before your NEXT edit/.test(sent[1] ?? ""));
  now += 30_000; editOk(handlers, "app/f99.py"); turn(handlers);
  check("K3: no third cadence message in the window", sent.length === 2);
  bash(handlers, "make verify", "all green");
  for (let i = 0; i < 5; i++) { now += 30_000; editOk(handlers, `app/g${i}.py`); turn(handlers); }
  check("K4: gate run resets the window (5 fresh files -> silent)", sent.length === 2);
}

{ // L: verification observed early -> no nudge
  const { handlers, sent } = makePi();
  editOk(handlers); redFail(handlers);
  for (let i = 0; i < 10; i++) { now += 60_000; editOk(handlers); turn(handlers); }
  check("L: red observed early -> no nudge (red-age not yet due)", sent.length === 0);
}

{ // M: hygiene restored — +55k context growth requests a hygiene checkpoint
  const { handlers, sent } = makePi();
  ctxTokens = 25_000;
  bash(handlers, "make verify", "all green"); // verifySeen — isolate the hygiene signal
  for (let i = 0; i < 9; i++) { now += 60_000; ctxTokens += 7_000; editOk(handlers); turn(handlers); }
  check("M: +55k ctx growth with MAX_HYGIENE=3 -> hygiene checkpoint", sent.length === 1 && /context grew/.test(sent[0] ?? ""));
  ctxTokens = 30_000;
}

{ // O1: 3 source files, zero tests, 15 min -> one TEST-NUDGE (verify-nudge suppressed via verifySeen)
  const { handlers, sent } = makePi();
  redFail(handlers); now += 10_000; bash(handlers, "make verify", "all ok"); // everRed=true, red cleared
  editOk(handlers, "app/models/a.py"); editOk(handlers, "app/services/b.py"); editOk(handlers, "app/routers/c.py");
  for (let i = 0; i < 15; i++) { now += 60_000; editOk(handlers, "app/models/a.py"); turn(handlers); }
  check("O1: 3 src / 0 tests / 15 min -> test nudge", sent.length === 1 && /no test files yet/.test(sent[0] ?? ""));
  for (let i = 0; i < 3; i++) { now += 60_000; editOk(handlers, "app/models/a.py"); turn(handlers); }
  check("O2: nudge fires only once", sent.length === 1);
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

{ // Q2: advancing failure signatures extend the red clock; absolute 20m ceiling backstops
  const { handlers, sent } = makePi();
  redFail(handlers); // full-gate red: opens the episode AND sets verifySeen
  let premature = false;
  for (let m = 1; m <= 19; m++) {
    now += 60_000;
    if (m % 4 === 0) bash(handlers, "pytest -q tests/a.py -x", `FAIL: sig-${m}`); // new signature
    editOk(handlers); turn(handlers);
    if (sent.length > 0) premature = true;
  }
  check("Q2a: 19 min of ADVANCING signatures -> no checkpoint (clock extended)", !premature);
  now += 90_000; editOk(handlers); turn(handlers); // past the 20m absolute ceiling
  check("Q2b: 20m total red -> ceiling checkpoint fired", sent.length === 1 && /stayed failing/.test(sent[0] ?? ""));
}

{ // Q3: subset runs do not reset the cadence window
  const { handlers, sent } = makePi();
  now += 60_000; bash(handlers, ".venv/bin/pytest -q tests/api/test_notice.py", "3 passed");
  // 경계 보정(2026-08-29 임계 통일): 조각 = 미검증 1~6파일, 7부터 기능 전체.
  for (let i = 0; i < 7; i++) { now += 30_000; editOk(handlers, `app/s${i}.py`); turn(handlers); }
  check("Q3: 7 unverified files with only subset greens -> cadence nudge", sent.length === 1 && /files have changed since the last full verification/.test(sent[0] ?? ""));
}

{ // R1: finish-block is uncapped and releases after a real gate run
  // 규모 보정(2026-08-28): 풀 게이트 요구는 이제 SMALL_FOOTPRINT 초과에서만 걸리므로 세 파일로 세운다.
  // 경계 보정(2026-08-29 임계 통일): 조각 = 미검증 1~6파일, 7부터 기능 전체.
  const { handlers, sent } = makePi();
  for (const f of ["a","b","c","d","e","f","g"]) editOk(handlers, `${f}.py`);
  turn(handlers); sent.length = 0; // 7파일이면 게이트 케이던스가 먼저 1회 나간다 — 소비하고 마감을 본다
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
    // 규약 위반 경고다. 완성도 경고("missing repository file")는 조각을 막지 않는다 — R2c 참고.
    content: [{ type: "text", text: "wrote ok <system-notice> [check-backend-naming] 1 issue(s): - app/x.py: bad name" }] }, ctx);
  handlers.turn_end({}, ctx);
  check("R2a: standing check-* notice after the gate -> FINISH-BLOCK",
    sent.length === 1 && /notice was raised after your last full verification/.test(sent[0] ?? ""));
  now += 10_000; bash(handlers, "make verify", "all green again");
  handlers.turn_end({}, ctx);
  check("R2b: fresh gate after the notice -> finish is silent", sent.length === 1);
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
  // 이 케이스의 계약은 "규모가 큰 변경에서는 verify-fast 가 풀 게이트를 대신하지 못한다" 이다.
  // 경계 보정(2026-08-29 임계 통일): 조각 = 미검증 1~6파일, 7부터 기능 전체.
  const { handlers, sent } = makePi();
  for (const f of ["a","b","c","d","e","f","g"]) editOk(handlers, `${f}.py`);
  turn(handlers); sent.length = 0; // 7파일이면 게이트 케이던스가 먼저 1회 나간다 — 소비하고 마감을 본다
  now += 10_000; bash(handlers, "make verify-fast", "all green");
  handlers.turn_end({}, ctx);
  check("R3: verify-fast green + prose finish -> FINISH-BLOCK stands",
    sent.length === 1 && /has not run since your last change/.test(sent[0] ?? ""));
}

{ // T1-T2: endgame tail trim — second idle green nudges once; a mutation re-arms the window
  const { handlers, sent } = makePi();
  editOk(handlers);
  redFail(handlers); // 진짜 작업 증거: red 를 본 적이 있어야 꼬리 윈도가 무장된다
  now += 10_000; bash(handlers, "make verify", "all green");
  now += 10_000; bash(handlers, "make verify", "all green again");
  check("T1: red seen + second idle green -> one TAIL-TRIM", sent.length === 1 && /Stop here/.test(sent[0] ?? ""));
  now += 10_000; bash(handlers, "make verify", "still green");
  check("T1b: third green -> no second message", sent.length === 1);
  now += 10_000; editOk(handlers, "app/fix.py");
  now += 10_000; bash(handlers, "make verify", "green after fix");
  now += 10_000; bash(handlers, "make verify", "green twice");
  check("T2: mutation re-armed the window -> tail fires again", sent.length === 2);
}

{ // T3: write→edit steering — a full write to a previously-read file gets one nudge
  const { handlers, sent } = makePi();
  handlers.tool_result({ toolName: "read", isError: false, input: { path: "app/services/old.py" }, content: [{ type: "text", text: "..." }] }, ctx);
  handlers.tool_result({ toolName: "write", isError: false, input: { path: "app/services/old.py" }, content: [{ type: "text", text: "wrote" }] }, ctx);
  check("T3: write over a read file -> one WRITE-STEER", sent.length === 1 && /prefer the edit tool/.test(sent[0] ?? ""));
  handlers.tool_result({ toolName: "write", isError: false, input: { path: "app/services/old.py" }, content: [{ type: "text", text: "wrote" }] }, ctx);
  check("T3b: same file again -> silent", sent.length === 1);
  handlers.tool_result({ toolName: "write", isError: false, input: { path: "app/new_file.py" }, content: [{ type: "text", text: "wrote" }] }, ctx);
  check("T3c: never-read (new) file -> silent", sent.length === 1);
}

{ // T4: TRUNC-RECOVERY — a truncated write gets chunked-append guidance once
  const { handlers, sent } = makePi();
  handlers.tool_result({ toolName: "write", isError: true, input: { path: "tests/api/test_big.py" }, content: [{ type: "text", text: "error: write truncated at 4096 tokens" }] }, ctx);
  check("T4: truncated write -> TRUNC-RECOVERY", sent.length === 1 && /append in chunks/.test(sent[0] ?? ""));
  handlers.tool_result({ toolName: "write", isError: true, input: { path: "tests/api/test_big.py" }, content: [{ type: "text", text: "error: write truncated again" }] }, ctx);
  check("T4b: same file -> once only", sent.length === 1);
}

{ // T5: baseline-green trap — no red ever, double green -> NO tail trim (measured 424s/0-artifact abort)
  const { handlers, sent } = makePi();
  editOk(handlers);
  now += 10_000; bash(handlers, "make verify", "all green");
  now += 10_000; bash(handlers, "make verify", "all green again");
  now += 10_000; bash(handlers, "make verify", "still green");
  check("T5: never-red session -> tail trim stays silent", sent.length === 0);
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
  // 이월된 게이트 뒤의 1파일 변경은 조각이다 — 마감은 침묵이고 다음 프롬프트가 이어받는다.
  check("X4: a 1-file change after the carried gate -> silent", p2.sent.length === 0);
}

{ // Y: 범위 존중 — 사용자가 기능의 한 조각만 시켰을 때 "아직 안 만든 것" 빨강으로 재구동하지 않는다.
  // 실측(2026-08-29): "모델과 스키마만" 프롬프트가 37.7분·123턴으로 부풀었다. 이 게이트는 도메인
  // 5계층·커버리지 100%를 요구하므로 조각 작업은 원리상 초록이 될 수 없다.
  const COMPLETE = "FAIL: notice: not imported in alembic/env.py | FAIL: notice: router not included in main.py";
  const BROKEN = "FAILED tests/api/test_notice.py::test_create - TypeError: 'NoneType' object";

  { const { handlers, sent } = makePi();          // 인터랙티브(BENCH_CELL 없음)
    now += 30_000; editOk(handlers, "models/notice.py"); editOk(handlers, "schemas/notice.py");
    bash(handlers, "make verify", COMPLETE);
    handlers.turn_end({}, ctx);
    // 계약 변경(2026-08-29): 고장 없는 조각의 마감은 침묵이다 — 조언 메시지도 다음 턴을 만든다.
    check("Y1: completeness-only red on a slice -> silent (no re-drive, no advice)", sent.length === 0);
    handlers.turn_end({}, ctx);
    check("Y2: it stays silent on repeat finishes", sent.length === 0); }

  { const { handlers, sent } = makePi();          // 고장이 섞이면 종전대로 재구동
    now += 30_000; editOk(handlers, "models/notice.py");
    bash(handlers, "make verify", `${COMPLETE}\n${BROKEN}`);
    handlers.turn_end({}, ctx);
    check("Y3: red with real breakage -> the END-GATE re-drive still fires",
      sent.length === 1 && /verification result was failing/.test(sent[0] ?? "")); }

  { process.env.BENCH_CELL = "1";                 // 벤치 셀: 과제가 언제나 기능 전체다
    const { handlers, sent } = makePi();
    now += 30_000; editOk(handlers, "models/notice.py");
    bash(handlers, "make verify", COMPLETE);
    handlers.turn_end({}, ctx);
    check("Y4: cell mode is unchanged (completeness red still re-drives)",
      sent.length === 1 && /verification result was failing/.test(sent[0] ?? ""));
    delete process.env.BENCH_CELL; }

  { const { handlers, sent } = makePi();          // 조각이 아니면(대형 변경) 종전대로
    now += 30_000;
    for (const f of ["a.py","b.py","c.py","d.py","e.py","f.py","g.py"]) editOk(handlers, f);
    bash(handlers, "make verify", COMPLETE);
    handlers.turn_end({}, ctx);
    // 실패한 게이트는 unverified 를 비우지 않으므로(2026-08-29 수정) 7파일이 그대로 남아
    // 먼저 게이트 케이던스가 나간다 — 그다음 턴에서 END-GATE 가 나오는 게 맞는 순서다.
    check("Y5a: a large unverified change first gets the gate cadence",
      sent.length === 1 && /files have changed since the last full verification/.test(sent[0] ?? ""));
    handlers.turn_end({}, ctx);
    check("Y5b: then the red finish is re-driven",
      sent.length === 2 && /verification result was failing/.test(sent[1] ?? "")); }
}

{ // Z: 실패한 게이트는 "검증됨" 이 아니다.
  // 실측 2026-08-29(4프롬프트 p4): 게이트 3회 중 마지막이 빨간 채로 세션이 끝났는데 마감 차단이
  // 침묵했다. lastGateAt 을 종료코드와 무관하게 밀고 있었기 때문이다. 최종 make verify 는
  // `conftest.py: model "notice" not imported` 한 줄로 exit 2 였다.
  { const { handlers, sent } = makePi();
    now += 30_000; editOk(handlers, "a.py");
    handlers.tool_result({ toolName: "bash", isError: true, input: { command: "make verify" },
      content: [{ type: "text", text: "make: *** [verify] Error 2" }] }, ctx);
    handlers.turn_end({}, ctx);
    check("Z1: a failing gate (unrecognised red) does not count as verification -> still blocked",
      sent.length === 1 && /verify-fast|make verify/.test(sent[0] ?? "")); }

  { const { handlers, sent } = makePi();
    now += 30_000; editOk(handlers, "a.py");
    bash(handlers, "make verify", "all green, 150 passed");
    handlers.turn_end({}, ctx);
    check("Z2: a passing gate still clears the finish", sent.length === 0); }
}

{ // W: 브리핑의 범위 문장은 인터랙티브에만 붙는다(셀의 과제는 언제나 기능 전체다).
  const brief = () => {
    const handlers = {}; const sent = [];
    try { rmSync(".omp/state/discipline.json"); } catch { /* 없으면 그만 */ }
    registerDiscipline({ on: (e, h) => { handlers[e] = h; }, sendUserMessage: (m) => sent.push(m) });
    handlers.turn_end({ toolResults: [{}] }, { getContextUsage: () => ({ tokens: 0 }) });
    return sent[0] ?? "";
  };
  const inter = brief();
  process.env.BENCH_CELL = "1";
  const cellBrief = brief();
  delete process.env.BENCH_CELL;
  check("W1: interactive brief tells the model to stay in scope", /stop there/.test(inter));
  check("W2: the cell brief carries no scope clause", !/stop there/.test(cellBrief));
  check("W3: the cell brief keeps the measured working pattern", /Working pattern that finishes/.test(cellBrief));
  // 모순 제거(2026-08-29): 인터랙티브 브리핑은 조각 작업에 루트 게이트를 요구하지 않는다.
  // 조각 상태의 루트 게이트는 원래 빨갛고, 초록을 요구하면 범위를 넘게 된다(p2 212초 -> 2867초).
  check("W4: interactive brief asks for a targeted run, not the root gate after each area",
    /verify-fast/.test(inter) && /root gate stays red/.test(inter) && !/after each area of work/.test(inter));
  check("W5: both briefs still forbid replacing a wiring line",
    /never replace an existing line/.test(inter) && /never replace an existing line/.test(cellBrief));
}

{ // V: 하위 디렉터리 게이트는 풀 게이트가 아니다(채점은 루트가 한다).
  // 실측 2026-08-29(4프롬프트 p4): `cd …/sandbox/backend && make verify` 11회로 초록을 봤지만
  // 루트 게이트는 `notice: router exists but api/notice.http is missing` 로 exit 2 였다.
  { const { handlers, sent } = makePi();
    now += 30_000;
    for (const f of ["a.py","b.py","c.py","d.py","e.py","f.py","g.py"]) editOk(handlers, f);
    turn(handlers); sent.length = 0; // 7파일이면 게이트 케이던스가 먼저 1회 나간다 — 소비하고 마감을 본다
    bash(handlers, "cd /Users/x/sandbox/backend && make verify 2>&1", "all green, 150 passed");
    handlers.turn_end({}, ctx);
    check("V1: a backend-scoped gate does not satisfy the finish check",
      sent.length === 1 && /has not run since your last change/.test(sent[0] ?? "")); }

  { const { handlers, sent } = makePi();
    now += 30_000; editOk(handlers, "a.py");
    now += 5_000;  // 검증은 편집보다 뒤여야 한다(같은 시각이면 덮은 것으로 보지 않는다)
    bash(handlers, "cd /Users/x/sandbox/backend && make verify 2>&1", "all green");
    handlers.turn_end({}, ctx);
    check("V2: but it does count as the targeted run for a small change", sent.length === 0); }

  { const { handlers, sent } = makePi();
    now += 30_000;
    for (const f of ["a.py","b.py","c.py","d.py","e.py","f.py","g.py"]) editOk(handlers, f);
    turn(handlers); sent.length = 0; // 7파일이면 게이트 케이던스가 먼저 1회 나간다 — 소비하고 마감을 본다
    bash(handlers, "make -C backend verify", "all green");
    handlers.turn_end({}, ctx);
    check("V3: `make -C backend verify` is scoped too",
      sent.length === 1 && /has not run since your last change/.test(sent[0] ?? "")); }

  { const { handlers, sent } = makePi();
    now += 30_000;
    for (const f of ["a.py","b.py","c.py"]) editOk(handlers, f);
    bash(handlers, "cd /Users/x/sandbox && make verify", "all green, 150 passed");
    handlers.turn_end({}, ctx);
    check("V4: the root gate still clears the finish", sent.length === 0); }
}

{ // S: 조각(slice)은 하나의 정의다 — 미검증 1~6파일. 세 호출부(마감·범위존중·케이던스)가 같은 경계를 쓴다.
  const COMPLETE = "FAIL: notice: not imported in alembic/env.py";
  const editN = (h, n, pre = "f") => { for (let i = 0; i < n; i++) editOk(h, `${pre}${i}.py`); };

  { const { handlers, sent } = makePi();
    now += 30_000; editN(handlers, 6);
    handlers.turn_end({}, ctx);
    check("S1: 6 files (largest slice) -> silent finish, no root-gate demand", sent.length === 0); }

  { const { handlers, sent } = makePi();
    now += 30_000; editN(handlers, 7);
    turn(handlers); sent.length = 0;
    handlers.turn_end({}, ctx);
    check("S2: 7 files (whole feature) -> the root gate is demanded",
      sent.length === 1 && /has not run since your last change/.test(sent[0] ?? "")); }

  { // 실측 회귀(2026-08-29 slice-a): 3파일 조각에 풀 게이트를 요구해 프롬프트가 부풀었다.
    const { handlers, sent } = makePi();
    now += 30_000;
    editOk(handlers, "app/models/notice.py"); editOk(handlers, "app/schemas/notice.py");
    editOk(handlers, "app/repositories/notice.py");
    bash(handlers, "make verify", COMPLETE);
    handlers.turn_end({}, ctx);
    check("S3: a 3-file slice with completeness-only red -> silent, no root-gate demand", sent.length === 0); }

  { // 임계를 다시 쪼개면 여기서 깨진다: 두 호출부가 모든 n 에서 같은 편에 서야 한다.
    let mismatch = null;
    for (let n = 1; n <= 8 && mismatch === null; n++) {
      const a = makePi();                       // (a) completeness 빨강으로 마감
      now += 30_000; editN(a.handlers, n, `a${n}_`);
      if (n > 6) turn(a.handlers);
      a.sent.length = 0;
      bash(a.handlers, "make verify", COMPLETE);
      a.handlers.turn_end({}, ctx);
      const aSlice = /rest of this feature does not exist yet/.test(a.sent[0] ?? "");

      const b = makePi();                       // (b) 게이트 없이 마감
      now += 30_000; editN(b.handlers, n, `b${n}_`);
      if (n > 6) turn(b.handlers);
      b.sent.length = 0;
      b.handlers.turn_end({}, ctx);
      const bSlice = /verify-fast/.test(b.sent[0] ?? "");
      if (aSlice !== bSlice) mismatch = n;
    }
    check("S4: scope respect and the finish check agree at every size (anti-resplit)", mismatch === null); }

  { const { handlers, sent } = makePi();
    for (let i = 0; i < 6; i++) { now += 30_000; editOk(handlers, `c${i}.py`); turn(handlers); }
    check("S5a: 6 unverified files -> no cadence nudge", sent.length === 0);
    now += 30_000; editOk(handlers, "c6.py"); turn(handlers);
    check("S5b: the 7th flips it -> exactly one nudge",
      sent.length === 1 && /files have changed since the last full verification/.test(sent[0] ?? "")); }

  { const { handlers, sent } = makePi();       // 카운터는 누적이 아니라 unverified 다
    now += 30_000; editN(handlers, 9, "d");
    turn(handlers); sent.length = 0;
    bash(handlers, "make verify", "all green, 150 passed");
    now += 10_000; editOk(handlers, "e0.py"); editOk(handlers, "e1.py");
    handlers.turn_end({}, ctx);
    check("S6: a green root gate resets the size -> the 2 files left finish silently", sent.length === 0); }

  { process.env.BENCH_CELL = "1";              // 셀은 타깃 마감 면제를 못 쓴다
    const { handlers, sent } = makePi();
    now += 30_000; editOk(handlers, "a.py");
    now += 5_000; bash(handlers, "make verify-fast", "3 passed");
    handlers.turn_end({}, ctx);
    check("S7: a cell never finishes on a targeted run",
      sent.length === 1 && /has not run since your last change/.test(sent[0] ?? ""));
    delete process.env.BENCH_CELL; }

  { const { handlers, sent } = makePi();       // 서 있는 경고는 크기와 무관하게 이긴다
    now += 30_000; editOk(handlers, "a.py");
    bash(handlers, "make verify", "all green");
    now += 5_000; editOk(handlers, "b.py");
    bash(handlers, "cat notice", "[check-backend-naming] found 1 issue in app/x.py");
    handlers.turn_end({}, ctx);
    check("S9: a standing check notice outranks the slice size",
      sent.length === 1 && /harness check notice/.test(sent[0] ?? "")); }
}

{ // SH: 셸로 만든 파일도 조각 크기에 들어간다.
  // 실측 2026-08-29(slice-b): 조각 프롬프트 하나에서 `untracked-mutation` 이 11회 찍혔다 —
  // 모델이 edit/write 도구 대신 heredoc 으로 쓴다. 집계에서 빠지면 조각 판정이 성립하지 않아
  // 마감이 다시 풀 게이트 요구로 빠진다.
  { const { handlers, sent } = makePi();
    now += 30_000;
    bash(handlers, "cat > backend/app/models/notice.py <<'PY'\nx\nPY", "");
    bash(handlers, "cat > backend/app/schemas/notice.py <<'PY'\nx\nPY", "");
    handlers.turn_end({}, ctx);
    check("SH1: two heredoc writes count as a 2-file slice -> silent finish", sent.length === 0); }

  { const { handlers, sent } = makePi();
    now += 30_000;
    for (let i = 0; i < 7; i++) bash(handlers, `cat > backend/app/f${i}.py <<'PY'\nx\nPY`, "");
    turn(handlers); sent.length = 0;
    handlers.turn_end({}, ctx);
    check("SH2: seven heredoc writes cross the slice boundary -> root gate demanded",
      sent.length === 1 && /has not run since your last change/.test(sent[0] ?? "")); }

  { const { handlers, sent } = makePi();
    now += 30_000; bash(handlers, "echo hi >> backend/app/models/notice.py", "");
    now += 5_000; bash(handlers, "ruff check backend/app | tee /tmp/out.txt", "All checks passed");
    handlers.turn_end({}, ctx);
    check("SH3: appends count, and a tee into /tmp does not", sent.length === 0); }

  { const { handlers, sent } = makePi();
    now += 30_000;
    bash(handlers, "cat > backend/app/models/notice.py <<'PY'\nx\nPY", "", true); // 실패한 명령
    handlers.turn_end({}, ctx);
    check("SH4: a failed shell write changes nothing", sent.length === 0 || !/verify/.test(sent[0] ?? "")); }
}

process.exit(failures ? 1 : 0);
