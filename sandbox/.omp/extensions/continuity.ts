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
 *  1) Stall — no successful mutation for STALL_TURNS turns OR STALL_MS wall
 *     time (long thinking/reading stretches with nothing landing).
 *  2) Red-age — a verification failure state persists for RED_AGE_TURNS turns
 *     OR RED_AGE_MS despite ongoing activity (the busy-loop: editing forever
 *     without returning to green). Healthy cells cycle red→green in minutes.
 *  3) End-gate — a prose-only turn (finishing signal) while red re-drives the
 *     model once via sendUserMessage at turn_end (agent_end is a teardown
 *     race and never generates — measured). Cap END_GATE_MAX.
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

const STALL_TURNS = 10;            // turns without a successful mutation
const STALL_MS = 7 * 60_000;       // wall time without a successful mutation
const RED_AGE_TURNS = 12;          // turns with a persisting red verification state
const RED_AGE_MS = 12 * 60_000;    // wall time with a persisting red state
const MAX_RESETS = 3;
const KEEP_RECENT = 4;
const END_GATE_MAX = 2;

export default function continuity(pi: any) {
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };

  let resets = 0, stallTurns = 0, endGateSends = 0;
  let lastProgressAt = Date.now();
  let redSig: string | null = null;
  let redCmdTk: Set<string> | null = null;
  let redSince = 0, redTurns = 0;
  let phase: "idle" | "checkpoint" | "cutting" = "idle";
  let armed = false;
  let bootstrap: string | null = null;

  log(`loaded two-phase. stall=${STALL_TURNS}t|${Math.round(STALL_MS / 60000)}m redAge=${RED_AGE_TURNS}t|${Math.round(RED_AGE_MS / 60000)}m maxResets=${MAX_RESETS} endGate=${END_GATE_MAX}`);

  function beginCheckpoint(reason: string) {
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
        const cmdTk = tokens(norm(str(event.input)).slice(0, 300));
        if (f) {
          if (!redSig) { redSince = Date.now(); redTurns = 0; }
          redSig = f; redCmdTk = cmdTk; log(`red: ${f.slice(0, 100)}`);
        } else if (!event.isError && redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5) {
          log("green — red cleared (same-command success)");
          redSig = null; redCmdTk = null; redSince = 0; redTurns = 0;
        }
      }
      if (!f && !event.isError && isMutating(event.toolName)) { stallTurns = 0; lastProgressAt = Date.now(); }
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  pi.on("turn_end", (e: any, _ctx: any) => {
    try {
      stallTurns++;
      if (redSig) redTurns++;
      const now = Date.now();

      if (phase === "checkpoint") {
        // The model has had one full turn to write its checkpoint — cut next.
        phase = "cutting"; armed = true;
        return;
      }
      if (phase === "idle" && resets < MAX_RESETS) {
        const stalled = stallTurns >= STALL_TURNS || now - lastProgressAt >= STALL_MS;
        const redAged = redSig !== null && (redTurns >= RED_AGE_TURNS || (redSince && now - redSince >= RED_AGE_MS));
        if (redAged) {
          beginCheckpoint(`the verification has stayed failing for ${redTurns} turns / ${Math.round((now - redSince) / 60000)} minutes while edits kept landing`);
          return;
        }
        if (stalled) {
          beginCheckpoint(stallTurns >= STALL_TURNS
            ? `no successful change landed for ${STALL_TURNS} turns`
            : `${Math.round((now - lastProgressAt) / 60000)} minutes passed with no successful change`);
          return;
        }
      }
      // End-gate only while no reset is in flight.
      const prose = !(e.toolResults && e.toolResults.length);
      if (phase === "idle" && prose && redSig && endGateSends < END_GATE_MAX) {
        endGateSends++;
        pi.sendUserMessage(`You just finished your answer, but the last observed verification result was failing:\n${redSig.slice(0, 300)}\nRe-run the verification to confirm it actually passes, and finish the remaining failures if any are left.`);
        log(`END-GATE re-drive #${endGateSends}`);
      }
    } catch (e2) { log(`turn_end ERR ${String(e2)}`); }
  });

  pi.on("context", (event: any, _ctx: any) => {
    if (!armed) return undefined;
    armed = false;
    try {
      const msgs = event.messages || [];
      const sys = msgs.filter((m: any) => m.role === "system");
      const recent = msgs.slice(-KEEP_RECENT);
      const bootMsg = { role: "user", content: bootstrap };
      const seen = new Set<any>();
      const kept = [...sys, bootMsg, ...recent].filter((m) => (seen.has(m) ? false : (seen.add(m), true)));
      resets++;
      phase = "idle";
      stallTurns = 0; lastProgressAt = Date.now();
      if (redSig) { redSince = Date.now(); redTurns = 0; }   // avoid immediate red-age re-fire
      log(`RESET context ${msgs.length} -> ${kept.length} (cut #${resets}, after checkpoint)`);
      return { messages: kept };
    } catch (e) { log(`context ERR ${String(e)}`); return undefined; }
  });

  pi.on("agent_end", (e: any) => log(`agent_end msgs=${(e.messages||[]).length} resets=${resets} endGate=${endGateSends} red=${redSig ? "YES" : "no"} phase=${phase}`));
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
