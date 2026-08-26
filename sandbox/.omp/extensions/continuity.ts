/**
 * continuity (two-phase) — workspace-local omp extension: a continuity safety
 * net that fires only in unhealthy sessions, and saves state BEFORE clearing.
 *
 * Lineage: stuck-reset v1-v3 → continuity (4 signals) → slim → two-phase
 * (2026-08-26). Two measured lessons drive this build:
 *  - A silent cell still failed as a busy-loop: 562 writes in 45m with verify
 *    almost never run (red 5 / green 1) — mutations keep landing, so a pure
 *    stall trigger never fires. Health is not "mutations happen"; it is
 *    "verification keeps returning to green".
 *  - The 4-signal build's resets were expensive (writes 70) because the cut
 *    came FIRST and the todo-update instruction came after — the model wrote
 *    its checkpoint from amnesia, then re-read files to rebuild state. State
 *    must be saved while the context still holds it, then cleared.
 *
 * Triggers (all sickness-only; healthy sessions pay zero):
 *  1) Stall — no successful mutation for STALL_MS wall time.
 *  2) Red-age — a verification failure state persists for RED_AGE_MS wall time
 *     despite ongoing activity (the busy-loop: editing forever without
 *     returning to green).
 *  Sickness is wall time only. Turn counts are not robust: they over-fire on
 *  fast turns (measured — 12 sub-5s red turns in 1 minute during a healthy
 *  verify-fix endgame; 10 sub-15s turns during a healthy read/plan stretch)
 *  and under-fire on slow thinking turns (3 x 3-minute turns is 9 stalled
 *  minutes but only 3 turns). Turn counters remain for logging.
 *  3) End-gate — a prose-only turn (finishing signal) while red re-drives the
 *     model once via sendUserMessage at turn_end (agent_end is a teardown
 *     race and never generates — measured). Cap END_GATE_MAX.
 *  4) Shift-left nudge — one reminder when files have been changing for
 *     VERIFY_NUDGE_MS with no verification observed. Measured: every
 *     near-miss cell ran its first verification 25+ minutes in, piling
 *     all failures into the finish.
 *
 * Reset is two-phase (save-then-clear, like hibernation):
 *  phase "checkpoint": with the context intact, ask the model to write the
 *    exact failure it is chasing, what it just tried, and the next single
 *    step into the todo list.
 *  phase "cut": on the following turn, rewrite the context to
 *    [system + bootstrap + last KEEP_RECENT]; the bootstrap points the model
 *    at the checkpoint it just wrote. The todo list survives natively.
 *
 * Safety: at most MAX_RESETS cuts. Tool-usage policy blocks are not task
 * failures. tool_result content arrives as [{type:"text",text}] — extract
 * text before matching. Loading: omp auto-discovers project-local
 * .omp/extensions/. Logging only when STUCK_RESET_LOG is set.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { appendFileSync } from "node:fs";

const STALL_MS = 7 * 60_000;       // wall time without a successful mutation (time only — see header)
const RED_AGE_MS = 12 * 60_000;    // wall time with a persisting red state (time only — see header)
const MAX_RESETS = 6;              // sickness cuts — save-then-clear made cuts cheap (measured), so headroom over 3
const HYGIENE_BUDGET = 50_000;     // session-token growth per two-phase hygiene cut
const MAX_HYGIENE = 0;             // ablation (2026-08-27): omp native compaction already trims at ~71k (measured, 48.5s); measuring whether our hygiene cuts were net cost — hook cells 6/6 TO vs hookless 2/2
const VERIFY_NUDGE_MS = 10 * 60_000; // shift-left: minutes of mutations tolerated before the one verification reminder
const KEEP_RECENT = 4;
const END_GATE_MAX = 2;

export default function continuity(pi: any) {
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };

  let resets = 0, stallTurns = 0, endGateSends = 0;
  let everRed = false, mutatedEver = false;
  let firstMutationAt = 0, verifyNudged = false;
  let lastProgressAt = Date.now();
  let redSig: string | null = null;
  let redCmdTk: Set<string> | null = null;
  let redSince = 0, redTurns = 0;
  let phase: "idle" | "checkpoint" | "cutting" = "idle";
  let cutKind: "sick" | "hygiene" = "sick";
  let cutIndex = -1;                 // persistent window: drop messages before this index
  let cutBootstrap: string | null = null;
  let hygieneCuts = 0;
  let lastTurnAt = Date.now();
  let tokensAtCut = 0;
  let armed = false;
  let bootstrap: string | null = null;

  log(`loaded two-phase. stall=${Math.round(STALL_MS / 60000)}m redAge=${Math.round(RED_AGE_MS / 60000)}m (time-only) maxResets=${MAX_RESETS} hygiene=${Math.round(HYGIENE_BUDGET/1000)}k x${MAX_HYGIENE} endGate=${END_GATE_MAX} verifyNudge=${Math.round(VERIFY_NUDGE_MS/60000)}m`);

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
        // Truncated pipelines (| tail/head/grep/...) hide FAIL lines and fake a
        // green run (measured: `make verify | tail -30` cleared red while the
        // gate still failed). Partial output is evidence of failure, never of
        // success — set red from it, but require an untruncated run to clear.
        const truncated = /\|\s*(?:tail|head|grep|sed|awk|wc)\b/.test(cmdStr);
        if (f) {
          if (!redSig) { redSince = Date.now(); redTurns = 0; }
          redSig = f; redCmdTk = cmdTk; everRed = true; log(`red: ${f.slice(0, 100)}`);
        } else if (!event.isError && !truncated && redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5) {
          log("green — red cleared (same-command success)");
          redSig = null; redCmdTk = null; redSince = 0; redTurns = 0;
        }
      }
      if (!f && !event.isError && isMutating(event.toolName)) { stallTurns = 0; lastProgressAt = Date.now(); mutatedEver = true; if (!firstMutationAt) firstMutationAt = Date.now(); }
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  pi.on("turn_end", (e: any, ctx: any) => {
    try {
      stallTurns++;
      if (redSig) redTurns++;
      const now = Date.now();
      // Instrumentation: per-turn wall interval and session token growth — the
      // data that decides the "context growth slows late turns" hypothesis.
      const used = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      log(`turn dt=${((now - lastTurnAt) / 1000).toFixed(1)}s ctx=${used}`);
      lastTurnAt = now;
      if (tokensAtCut === 0 && used > 0) tokensAtCut = used;

      if (phase === "checkpoint") {
        // The model has had one full turn to write its checkpoint. If the
        // sickness resolved inside that turn (verification back to green, or a
        // change just landed — measured: red cleared in the checkpoint window
        // and the cut still fired after green), cancel instead of cutting.
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
      // Shift-left verification nudge (once per session): failures found at
      // minute 15 are fixed inside the cap; the same failures found at minute
      // 30 pile into a near-miss (measured across every hook cell).
      if (phase === "idle" && firstMutationAt > 0 && !everRed && !verifyNudged && now - firstMutationAt >= VERIFY_NUDGE_MS) {
        verifyNudged = true;
        pi.sendUserMessage(`Files have been changing for ~${Math.round(VERIFY_NUDGE_MS / 60000)} minutes with no verification run observed. Run the project's verification now — failures found early are cheaper than a pile at the end. Then continue working.`);
        log("VERIFY-NUDGE sent");
        return;
      }
      // Hypothesis lever (two-phase hygiene): the old cut-first hygiene cost more than
      // it saved; with save-then-clear the price dropped, so re-test whether trimming a
      // grown context buys back late-turn speed.
      if (phase === "idle" && hygieneCuts < MAX_HYGIENE && tokensAtCut > 0 && used - tokensAtCut >= HYGIENE_BUDGET) {
        beginCheckpoint(`the context grew by ~${Math.round((used - tokensAtCut) / 1000)}k tokens since the last cut`, "hygiene");
        return;
      }
      // End-gate only while no reset is in flight. Two blind-finish shapes
      // (both measured): finishing while the last verification was red, and
      // finishing after mutations with no verification observed at all.
      const prose = !(e.toolResults && e.toolResults.length);
      if (phase === "idle" && prose && endGateSends < END_GATE_MAX) {
        if (redSig) {
          endGateSends++;
          pi.sendUserMessage(`You just finished your answer, but the last observed verification result was failing:\n${redSig.slice(0, 300)}\nRe-run the verification to confirm it actually passes, and finish the remaining failures if any are left.`);
          log(`END-GATE re-drive #${endGateSends}`);
        } else if (mutatedEver && !everRed) {
          endGateSends++;
          pi.sendUserMessage(`You are finishing, but files were changed and no verification run has been observed this session. Run the project's verification now and confirm it passes before finishing.`);
          log(`END-GATE verify-unseen #${endGateSends}`);
        }
      }
    } catch (e2) { log(`turn_end ERR ${String(e2)}`); }
  });

  pi.on("context", (event: any, ctx: any) => {
    try {
      const msgs = event.messages || [];
      if (armed) {
        // Measured: a one-shot rewrite lasts a single model call — the stored
        // session returns in full on the next one (ctx 80k -> 22k -> 81k in the
        // turn log). A cut must persist: remember the boundary and keep
        // windowing every later call until a newer cut supersedes it.
        armed = false;
        cutIndex = Math.max(0, msgs.length - KEEP_RECENT);
        cutBootstrap = bootstrap;
        if (cutKind === "hygiene") hygieneCuts++; else resets++;
        tokensAtCut = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
        phase = "idle";
        stallTurns = 0; lastProgressAt = Date.now();
        if (redSig) { redSince = Date.now(); redTurns = 0; }   // avoid immediate red-age re-fire
        log(`RESET window @${cutIndex}/${msgs.length} (${cutKind} cut, sick#${resets} hyg#${hygieneCuts}, after checkpoint)`);
      }
      if (cutIndex < 0) return undefined;
      if (cutIndex > msgs.length) { cutIndex = -1; return undefined; }  // session rewritten under us — drop the marker
      const sys = msgs.filter((m: any) => m.role === "system");
      const bootMsg = { role: "user", content: cutBootstrap };
      const seen = new Set<any>();
      const kept = [...sys, bootMsg, ...msgs.slice(cutIndex)].filter((m) => (seen.has(m) ? false : (seen.add(m), true)));
      return { messages: kept };
    } catch (e) { log(`context ERR ${String(e)}`); return undefined; }
  });

  pi.on("agent_end", (e: any) => {
    log(`agent_end msgs=${(e.messages||[]).length} resets=${resets} endGate=${endGateSends} red=${redSig ? "YES" : "no"} phase=${phase}`);
    // A finished session must not be re-driven by our own machinery: the
    // injected bootstrap user message can reopen the loop after agent_end
    // (measured — post-green turns kept running until the cap). Release the
    // window and any in-flight cut; a deliberate revival sees the full session.
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
