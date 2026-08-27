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
 *  - Guards: truncated pipelines (| tail/head/...) never clear red (measured
 *    fake green via `make verify | tail -30`); tool-policy blocks are not
 *    task failures.
 *
 * Knobs are fixed constants (local bench target only — the config/profile
 * layer was reverted by user decision). Logging only when STUCK_RESET_LOG set.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { appendFileSync } from "node:fs";

const STALL_MS = 7 * 60_000;         // wall time without a successful mutation
const RED_AGE_MS = 12 * 60_000;      // wall time with a persisting red state
const MAX_RESETS = 6;                // sickness-cut backstop
const HYGIENE_BUDGET = 50_000;       // session-token growth per hygiene cut
const MAX_HYGIENE = 3;
const KEEP_RECENT = 4;               // messages kept across a cut
const END_GATE_MAX = 2;              // red-finish re-drives
const VERIFY_NUDGE_MS = 10 * 60_000; // mutations tolerated before the one verify reminder
const TEST_NUDGE_MS = 15 * 60_000;   // source-only mutations tolerated before the one test reminder
const SRC_BEFORE_TESTS = 3;          // distinct source files that make missing tests a signal

export function registerDiscipline(pi: any): void {
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };

  let resets = 0, stallTurns = 0, endGateSends = 0;
  let everRed = false, mutatedEver = false;
  let firstMutationAt = 0, verifyNudged = false, testNudged = false, finishChecked = false;
  const srcWritten = new Set<string>();
  const testWritten = new Set<string>();
  let lastProgressAt = Date.now();
  let redSig: string | null = null;
  let redCmdTk: Set<string> | null = null;
  let redSince = 0, redTurns = 0;
  let phase: "idle" | "checkpoint" | "cutting" = "idle";
  let cutKind: "sick" | "hygiene" = "sick";
  let cutIndex = -1;
  let cutBootstrap: string | null = null;
  let hygieneCuts = 0;
  let lastTurnAt = Date.now();
  let tokensAtCut = 0;
  let armed = false;
  let bootstrap: string | null = null;

  log(`loaded discipline. stall=${Math.round(STALL_MS / 60000)}m redAge=${Math.round(RED_AGE_MS / 60000)}m (time-only) maxResets=${MAX_RESETS} hygiene=${Math.round(HYGIENE_BUDGET / 1000)}k x${MAX_HYGIENE} endGate=${END_GATE_MAX} verifyNudge=${Math.round(VERIFY_NUDGE_MS / 60000)}m testNudge=${Math.round(TEST_NUDGE_MS / 60000)}m/${SRC_BEFORE_TESTS}src`);

  function beginCheckpoint(reason: string, kind: "sick" | "hygiene" = "sick") {
    cutKind = kind;
    phase = "checkpoint";
    bootstrap = `[continuity] Context was cleared because ${reason}. The system prompt is unchanged, `
      + `and the todo list holds the checkpoint you just wrote — read it and continue from there.\n`
      + `Step back, reconsider the approach, and continue the remaining work a different way. `
      + `Re-run the project's verification early to confirm where things stand.`;
    pi.sendUserMessage(`[continuity] Checkpoint before a context reset (${reason}). `
      + `Update the todo list in detail NOW, while you still have full context: `
      + `the exact failure you are chasing (quote its message), what you just tried, `
      + `and the next single step. Then continue.`);
    log(`CHECKPOINT requested (${reason})`);
  }

  pi.on("tool_result", (event: any, _ctx: any) => {
    try {
      const content = contentText(event.content);
      if (event.isError && isPolicyBlock(content)) return;
      const f = failSig(content);
      if (/^bash/i.test(event.toolName)) {
        const cmdStr = norm(str(event.input)).slice(0, 300);
        const cmdTk = tokens(cmdStr);
        const truncated = /\|\s*(?:tail|head|grep|sed|awk|wc)\b/.test(cmdStr);
        if (f) {
          if (!redSig) { redSince = Date.now(); redTurns = 0; }
          redSig = f; redCmdTk = cmdTk; everRed = true; log(`red: ${f.slice(0, 100)}`);
        } else if (!event.isError && !truncated && redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5) {
          log("green — red cleared (same-command success)");
          redSig = null; redCmdTk = null; redSince = 0; redTurns = 0;
        }
      }
      if (!f && !event.isError && isMutating(event.toolName)) {
        stallTurns = 0; lastProgressAt = Date.now(); mutatedEver = true;
        if (!firstMutationAt) firstMutationAt = Date.now();
        const path = String(event.input?.path ?? "");
        if (path) (/(^|\/)tests?\//.test(path) ? testWritten : srcWritten).add(path);
      }
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  pi.on("turn_end", (e: any, ctx: any) => {
    try {
      stallTurns++;
      if (redSig) redTurns++;
      const now = Date.now();
      const used = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      log(`turn dt=${((now - lastTurnAt) / 1000).toFixed(1)}s ctx=${used}`);
      lastTurnAt = now;
      if (tokensAtCut === 0 && used > 0) tokensAtCut = used;

      if (phase === "checkpoint") {
        if (cutKind === "sick" && redSig === null && now - lastProgressAt < STALL_MS) {
          phase = "idle"; bootstrap = null;
          log("CHECKPOINT canceled (recovered before the cut)");
          return;
        }
        phase = "cutting"; armed = true;
        return;
      }
      if (phase === "idle" && resets < MAX_RESETS) {
        const stalled = now - lastProgressAt >= STALL_MS;
        const redAged = redSig !== null && redSince > 0 && now - redSince >= RED_AGE_MS;
        if (redAged) {
          beginCheckpoint(`the verification has stayed failing for ${redTurns} turns / ${Math.round((now - redSince) / 60000)} minutes while edits kept landing`);
          return;
        }
        if (stalled) {
          beginCheckpoint(`${Math.round((now - lastProgressAt) / 60000)} minutes (${stallTurns} turns) passed with no successful change`);
          return;
        }
      }
      if (phase === "idle" && firstMutationAt > 0 && !everRed && !verifyNudged && now - firstMutationAt >= VERIFY_NUDGE_MS) {
        verifyNudged = true;
        pi.sendUserMessage(`Files have been changing for ~${Math.round(VERIFY_NUDGE_MS / 60000)} minutes with no verification run observed. Run the project's verification now — failures found early are cheaper than a pile at the end. Then continue working.`);
        log("VERIFY-NUDGE sent");
        return;
      }
      if (phase === "idle" && !testNudged && srcWritten.size >= SRC_BEFORE_TESTS && testWritten.size === 0 && firstMutationAt > 0 && now - firstMutationAt >= TEST_NUDGE_MS) {
        testNudged = true;
        pi.sendUserMessage(`You have written ${srcWritten.size} source files and no test files yet. Tests are part of the deliverable and the gate requires them at full coverage — write the sibling tests for what already exists NOW, before adding more source. A test written next to fresh code does not guess at names that do not exist.`);
        log("TEST-NUDGE sent");
        return;
      }
      if (phase === "idle" && hygieneCuts < MAX_HYGIENE && tokensAtCut > 0 && used - tokensAtCut >= HYGIENE_BUDGET) {
        beginCheckpoint(`the context grew by ~${Math.round((used - tokensAtCut) / 1000)}k tokens since the last cut`, "hygiene");
        return;
      }
      const prose = !(e.toolResults && e.toolResults.length);
      if (phase === "idle" && prose && endGateSends < END_GATE_MAX) {
        if (redSig) {
          endGateSends++;
          pi.sendUserMessage(`You just finished your answer, but the last observed verification result was failing:\n${redSig.slice(0, 300)}\nRe-run the verification to confirm it actually passes, and finish the remaining failures if any are left.`);
          log(`END-GATE re-drive #${endGateSends}`);
        } else if (mutatedEver && !finishChecked) {
          finishChecked = true;
          pi.sendUserMessage(`Final check before finishing: run the project's full verification once end-to-end and confirm it is green. A passing subset or an earlier run does not count — the gate needs a fresh full pass. If it fails, finish the remaining failures first.`);
          log("END-GATE finish-check");
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
        if (cutKind === "hygiene") hygieneCuts++; else resets++;
        tokensAtCut = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
        phase = "idle";
        stallTurns = 0; lastProgressAt = Date.now();
        if (redSig) { redSince = Date.now(); redTurns = 0; }
        log(`RESET window @${cutIndex}/${msgs.length} (${cutKind} cut, sick#${resets} hyg#${hygieneCuts}, after checkpoint)`);
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
    log(`agent_end msgs=${(e.messages||[]).length} resets=${resets} endGate=${endGateSends} red=${redSig ? "YES" : "no"} phase=${phase}`);
    cutIndex = -1; cutBootstrap = null; phase = "idle"; armed = false; bootstrap = null;
  });
}

// ---- helpers (details after the entry point — check-code-layout) ----
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
