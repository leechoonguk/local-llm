/**
 * Session Discipline (bench continuity) — integrated into the continuity package.
 *
 * History: born as the standalone `extensions/continuity.ts` bench hook and
 * merged here (2026-08-27) next to the resident package it always ran beside.
 * `registerDiscipline(pi)` is called from `index.ts`; state is independent of
 * the package's own goal/loop machinery.
 *
 * What it does (all measured on the REST bench, see bench/2026-08-2*.md):
 *  - Shift-left nudge: one reminder when files have been changing for
 *    verifyNudgeMs with no verification observed (near-miss cells ran their
 *    first verification 25+ minutes in).
 *  - Sickness cuts, wall-time only (turn counts over-fire on fast turns and
 *    under-fire on slow ones): stall (no successful mutation for stallMs) and
 *    red-age (a failing verification persisting redAgeMs). Cuts are two-phase
 *    (checkpoint-then-clear) and windows persist until superseded or released.
 *  - Hygiene cuts: trim a context that grew hygieneBudget tokens since the
 *    last cut — 6.5s vs omp compaction's 48.5s, and dt recovers 2-4x.
 *  - End-gates: finishing while red gets re-driven (endGateMax); any mutated
 *    finish gets ONE final-full-verification re-drive (a passing subset
 *    legitimately cleared red while the gate still failed — scope green).
 *  - Guards: truncated pipelines (| tail/head/...) never clear red; a pending
 *    sick checkpoint cancels if the session recovers first; agent_end releases
 *    the window so a finished session is not re-driven by our own bootstrap.
 *
 * Configuration (session-start dynamic): `.omp/continuity.json` at the
 * workspace root, shape { "discipline": {<knob overrides>}, "profiles":
 * {"<name>": {<overrides>}} }. `CONTINUITY_PROFILE=<name>` selects a profile
 * on top of the base overrides — e.g. a frontier-model profile can set
 * maxHygiene 0 (context cuts break provider prompt caches) or enabled false.
 * Sick cuts are rate-limited by sickCooldownMs instead of a small absolute
 * cap: long sessions earn more interventions, loops still cannot spin.
 * Logging only when STUCK_RESET_LOG is set.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { appendFileSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

const DEFAULTS = {
  enabled: true,
  stallMs: 7 * 60_000,        // wall time without a successful mutation
  redAgeMs: 12 * 60_000,      // wall time with a persisting red state
  sickCooldownMs: 5 * 60_000, // minimum spacing between sickness cuts
  maxResets: 12,              // absolute backstop, far above any healthy session
  hygieneBudget: 50_000,      // session-token growth per two-phase hygiene cut
  maxHygiene: 3,
  keepRecent: 4,
  endGateMax: 2,
  verifyNudgeMs: 10 * 60_000, // minutes of mutations tolerated before the one reminder
};

export function registerDiscipline(pi: any): void {
  const K = loadKnobs();
  const logPath = process.env.STUCK_RESET_LOG || "";
  const log = (s: string) => { if (logPath) { try { appendFileSync(logPath, `[continuity] ${s}\n`); } catch {} } };
  if (!K.enabled) { log("discipline disabled by config"); return; }

  let resets = 0, stallTurns = 0, endGateSends = 0;
  let everRed = false, mutatedEver = false;
  let firstMutationAt = 0, verifyNudged = false, finishChecked = false;
  let lastProgressAt = Date.now();
  let lastSickCutAt = 0;
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

  log(`loaded discipline. stall=${Math.round(K.stallMs / 60000)}m redAge=${Math.round(K.redAgeMs / 60000)}m (time-only) cooldown=${Math.round(K.sickCooldownMs / 60000)}m backstop=${K.maxResets} hygiene=${Math.round(K.hygieneBudget / 1000)}k x${K.maxHygiene} endGate=${K.endGateMax} verifyNudge=${Math.round(K.verifyNudgeMs / 60000)}m`);

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
      // data that decided the "context growth slows late turns" hypothesis.
      const used = (() => { try { return ctx.getContextUsage?.()?.tokens ?? 0; } catch { return 0; } })();
      log(`turn dt=${((now - lastTurnAt) / 1000).toFixed(1)}s ctx=${used}`);
      lastTurnAt = now;
      if (tokensAtCut === 0 && used > 0) tokensAtCut = used;

      if (phase === "checkpoint") {
        // The model has had one full turn to write its checkpoint. If the
        // sickness resolved inside that turn (verification back to green, or a
        // change just landed — measured: red cleared in the checkpoint window
        // and the cut still fired after green), cancel instead of cutting.
        if (cutKind === "sick" && redSig === null && now - lastProgressAt < K.stallMs) {
          phase = "idle"; bootstrap = null;
          log("CHECKPOINT canceled (recovered before the cut)");
          return;
        }
        phase = "cutting"; armed = true;
        return;
      }
      if (phase === "idle" && resets < K.maxResets && now - lastSickCutAt >= K.sickCooldownMs) {
        const stalled = now - lastProgressAt >= K.stallMs;
        const redAged = redSig !== null && redSince > 0 && now - redSince >= K.redAgeMs;
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
      if (phase === "idle" && firstMutationAt > 0 && !everRed && !verifyNudged && now - firstMutationAt >= K.verifyNudgeMs) {
        verifyNudged = true;
        pi.sendUserMessage(`Files have been changing for ~${Math.round(K.verifyNudgeMs / 60000)} minutes with no verification run observed. Run the project's verification now — failures found early are cheaper than a pile at the end. Then continue working.`);
        log("VERIFY-NUDGE sent");
        return;
      }
      // Hypothesis lever (two-phase hygiene): the old cut-first hygiene cost more than
      // it saved; with save-then-clear the price dropped, so re-test whether trimming a
      // grown context buys back late-turn speed.
      if (phase === "idle" && hygieneCuts < K.maxHygiene && tokensAtCut > 0 && used - tokensAtCut >= K.hygieneBudget) {
        beginCheckpoint(`the context grew by ~${Math.round((used - tokensAtCut) / 1000)}k tokens since the last cut`, "hygiene");
        return;
      }
      // End-gate only while no reset is in flight. Two blind-finish shapes
      // (both measured): finishing while the last verification was red, and
      // finishing after mutations with no fresh full verification.
      const prose = !(e.toolResults && e.toolResults.length);
      if (phase === "idle" && prose && endGateSends < K.endGateMax) {
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
        // Measured: a one-shot rewrite lasts a single model call — the stored
        // session returns in full on the next one (ctx 80k -> 22k -> 81k in the
        // turn log). A cut must persist: remember the boundary and keep
        // windowing every later call until a newer cut supersedes it.
        armed = false;
        cutIndex = Math.max(0, msgs.length - K.keepRecent);
        cutBootstrap = bootstrap;
        if (cutKind === "hygiene") hygieneCuts++; else { resets++; lastSickCutAt = Date.now(); }
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
function loadKnobs(): typeof DEFAULTS {
  try {
    const raw = readFileSync(join(process.cwd(), ".omp", "continuity.json"), "utf-8");
    const cfg = JSON.parse(raw);
    const profile = process.env.CONTINUITY_PROFILE;
    const fromProfile = profile && cfg.profiles && cfg.profiles[profile] ? cfg.profiles[profile] : {};
    return { ...DEFAULTS, ...(cfg.discipline ?? {}), ...fromProfile };
  } catch { return { ...DEFAULTS }; }
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
