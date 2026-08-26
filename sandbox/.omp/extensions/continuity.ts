/**
 * continuity (slim) — workspace-local omp extension: a continuity safety net
 * that fires only in unhealthy sessions.
 *
 * Lineage: stuck-reset v1-v3 → continuity (4 signals) → slimmed (2026-08-26).
 * Measured on the repaired sandbox harness: hygiene (context-size) and
 * similarity resets fire during perfectly healthy work, and each reset costs
 * re-reads (churn) — hookless baseline went 2/2 green (39.5m/41.2m) while the
 * 4-signal hook timed out a cell at 45m with writes 70. Triggers that cannot
 * tell health from sickness are removed; the two that by definition only fire
 * when nothing is working remain — so a healthy session pays zero cost.
 *
 *  1) Stall reset (dual trigger): when no successful mutation (file write/edit
 *     or error-free bash) has landed for STALL_TURNS turns OR STALL_MS wall
 *     time, rewrite the context to [system + neutral bootstrap + last
 *     KEEP_RECENT messages]. The time axis catches long-thinking stretches
 *     where few turns burn many minutes. The bootstrap prescribes nothing —
 *     it tells the model to update its todo (the task's memory), step back,
 *     and try a different approach; what to fix stays the model's decision.
 *  2) End-gate: record verification failures (FAIL/ERROR lines in bash
 *     output) as a red state, cleared only when a *similar* command succeeds
 *     (clearing on any bash success neutered the gate — measured bug). If the
 *     model produces a prose-only turn (a finishing signal) while red,
 *     re-drive once via sendUserMessage at turn_end (cap END_GATE_MAX).
 *     Injecting at agent_end is a teardown race and never generates (measured).
 *
 * Safety: at most MAX_RESETS resets. Tool-usage policy blocks ("use read
 * instead of cat") are not task failures and are excluded. tool_result
 * content arrives as [{type:"text",text}] — extract text before matching
 * (measured: serialized JSON hides line starts from the FAIL regex).
 * Loading: omp auto-discovers project-local .omp/extensions/, so bench and
 * real work run the same configuration with no opt-in flag. Logging only
 * when STUCK_RESET_LOG is set.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { appendFileSync } from "node:fs";

const STALL_TURNS = 10;            // turns without a successful mutation
const STALL_MS = 7 * 60_000;       // wall time without a successful mutation
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
  let armed = false;
  let bootstrap: string | null = null;

  log(`loaded slim. stall=${STALL_TURNS}t|${Math.round(STALL_MS / 60000)}m maxResets=${MAX_RESETS} endGate=${END_GATE_MAX}`);

  function arm(reason: string) {
    if (resets >= MAX_RESETS) { log(`MAX_RESETS — no reset (${reason})`); return; }
    bootstrap = `[continuity] Context was cleared because ${reason}. The system prompt is unchanged.\n`
      + `Before continuing, update the todo list first — record what is done, what remains, and the current state. The todo list is this task's memory.\n`
      + `Then step back, reconsider the approach, and continue the remaining work a different way. Re-run the project's verification if needed.`;
    armed = true; resets++;
    lastProgressAt = Date.now(); stallTurns = 0;   // avoid immediate re-fire after a reset
    log(`ARMED reset #${resets} (${reason})`);
  }

  pi.on("tool_result", (event: any, _ctx: any) => {
    try {
      const content = contentText(event.content);
      if (event.isError && isPolicyBlock(content)) return;
      const f = failSig(content);
      if (/^bash/i.test(event.toolName)) {
        const cmdTk = tokens(norm(str(event.input)).slice(0, 300));
        if (f) { redSig = f; redCmdTk = cmdTk; log(`red: ${f.slice(0, 100)}`); }
        else if (!event.isError && redSig && redCmdTk && jaccard(cmdTk, redCmdTk) >= 0.5) {
          log("green — red cleared (same-command success)"); redSig = null; redCmdTk = null;
        }
      }
      if (!f && !event.isError && isMutating(event.toolName)) { stallTurns = 0; lastProgressAt = Date.now(); }
    } catch (e) { log(`tool_result ERR ${String(e)}`); }
  });

  pi.on("turn_end", (e: any, _ctx: any) => {
    try {
      stallTurns++;
      const stalledMs = Date.now() - lastProgressAt;
      if (!armed && resets < MAX_RESETS && (stallTurns >= STALL_TURNS || stalledMs >= STALL_MS)) {
        arm(stallTurns >= STALL_TURNS
          ? `no successful change landed for ${STALL_TURNS} turns`
          : `${Math.round(stalledMs / 60000)} minutes passed with no successful change`);
      }
      const prose = !(e.toolResults && e.toolResults.length);
      if (prose && redSig && endGateSends < END_GATE_MAX) {
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
      log(`RESET context ${msgs.length} -> ${kept.length}`);
      return { messages: kept };
    } catch (e) { log(`context ERR ${String(e)}`); return undefined; }
  });

  pi.on("agent_end", (e: any) => log(`agent_end msgs=${(e.messages||[]).length} resets=${resets} endGate=${endGateSends} red=${redSig ? "YES" : "no"}`));
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
