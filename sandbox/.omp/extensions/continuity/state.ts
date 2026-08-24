/**
 * Continuity State
 *
 * The goal card and the evidence behind it, persisted twice on purpose:
 *
 *   1. as a session custom entry, so it survives compaction and is rebuildable
 *      from `ctx.sessionManager.getBranch()` after a resume or a branch;
 *   2. as `.omp/state/<session>.continuity.json`, because a *new* session (the
 *      handoff path) inherits no memory, and because `make continuity-report`
 *      reads across sessions. The owner is in the filename, not a directory:
 *      `.omp/state/` is keyed by session id, so a bare `<session>.json` would
 *      silently collide the day a second extension stores state there.
 *
 * Everything here is mechanical. No model writes this state, so a small local
 * model cannot corrupt it, and a compaction whose summarizer failed can still be
 * answered with a summary built from it.
 *
 * Both sources are persisted blobs written by an older version of this code, so
 * every field is narrowed on the way in rather than asserted.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { dirname, join } from "node:path";

// ============================================================
// Constants
// ============================================================

/** Reverse-domain namespace: `customType` is a global namespace in OMP. */
export const ENTRY_TYPE = "dev.fast-api-standard.continuity/v1";

/** Bounded, so the state never becomes the thing that overflows the context. */
const MAX_FACTS = 24;
const MAX_LOOPS = 12;
const MAX_INTERVENTIONS = 16;

/** Owner tag in the filename — `.omp/state/` is a shared, session-keyed space. */
export const STATE_SUFFIX = ".continuity.json";
const MAX_TEXT = 400;

// ============================================================
// Types
// ============================================================

/**
 * `blind` is the goal-driven one: the acceptance names a file, the file is not
 * there, and the session has not written anything for several turns. Loops are
 * detected from repetition; this is detected from the target.
 */
export type LoopKind = "repeat" | "oscillation" | "errorLoop" | "stall" | "thrash" | "blind";

export interface LoopEvidence {
  sig: string;
  kind: LoopKind;
  count: number;
  detail: string;
}

/** What an intervention did, once the next turns have answered. */
export type InterventionOutcome = "pending" | "broke" | "failed";

/**
 * One intervention and what happened after it. This is the only way to know
 * whether a threshold is right: an intervention that never breaks a loop is a
 * steer the session paid for and learned nothing from, and one that always
 * breaks it may be firing later than it needs to.
 */
export interface Intervention {
  turn: number;
  escalation: number;
  kinds: LoopKind[];
  sigs: string[];
  /** Loop counts at the moment of the intervention — the threshold evidence. */
  counts: number[];
  outcome: InterventionOutcome;
  /** Turns between the intervention and its outcome. */
  turnsToOutcome: number | null;
  /**
   * Files read for the first time in the turns after the intervention. A
   * `stall` is declared when nothing was written and no fact was recorded, so a
   * session reading its way through unfamiliar code looks identical to one that
   * is stuck. The count separates a wrong signal (it was research) from a wrong
   * answer (the steer did not help).
   */
  newPathsAfter: number;
}

export interface ContinuityState {
  v: 1;
  goal: string;
  facts: string[];
  nextAction: string;
  banned: string[];
  loops: LoopEvidence[];
  escalation: number;
  turns: number;
  toolCalls: number;
  compactions: number;
  recoveries: number;
  interventions: Intervention[];
  /** Compaction requests this extension made, newest last: "why" or "why:declined". */
  requests: string[];
  /**
   * The throwaway agent directory a probe ran under, empty for a real session.
   * A probe drives behaviour on purpose, so counting it as a sample poisons the
   * one table that decides thresholds — measured, a deliberate thrash probe
   * appeared in `make continuity-report` beside real work.
   */
  agentDir: string;
  /**
   * What the profile last read from the runtime, as
   * `<profile> <percent>% <tokens>/<window>`. A threshold that never fires is
   * indistinguishable from one that cannot read its input without this.
   */
  lastUsage: string;
  /**
   * The acceptance this session is armed with, as declared - predicate objects,
   * not rebuilt types, because state crosses a JSON boundary.
   *
   * It lives here so a **resumed** session is armed by its own history. Held
   * only in a local variable it was lost on every restart, which is exactly when
   * a long goal needs it: the session came back knowing its goal and no longer
   * knowing what would prove it.
   */
  acceptance: unknown[];
  /** Wall-clock instant the armed budget runs out, or 0 when none was set. */
  deadlineMs: number;
  startedAt: number;
}

// ============================================================
// Functions
// ============================================================

export function emptyState(): ContinuityState {
  return {
    v: 1,
    goal: "",
    facts: [],
    nextAction: "",
    banned: [],
    loops: [],
    escalation: 0,
    turns: 0,
    toolCalls: 0,
    compactions: 0,
    recoveries: 0,
    interventions: [],
    requests: [],
    lastUsage: "",
    acceptance: [],
    deadlineMs: 0,
    agentDir: "",
    startedAt: Date.now(),
  };
}

/**
 * Rebuilds state from the branch: the newest continuity entry wins, and a
 * compaction's `preserveData` counts when it is newer — compaction is exactly
 * the moment a session's live memory is thrown away.
 */
export function restoreFromBranch(entries: unknown[]): ContinuityState {
  let state = emptyState();
  for (const entry of entries) {
    if (entry === null || typeof entry !== "object") continue;
    const kind = "type" in entry ? entry.type : undefined;

    if (kind === "custom" && "customType" in entry && entry.customType === ENTRY_TYPE && "data" in entry) {
      state = merge(state, entry.data);
      continue;
    }
    if (kind !== "compaction" || !("preserveData" in entry)) continue;
    const preserved = entry.preserveData;
    if (preserved === null || typeof preserved !== "object" || !("continuity" in preserved)) continue;
    state = merge(state, preserved.continuity);
  }
  return state;
}

/** File persistence keyed by session id — the only path a new session can read. */
export function loadFromDisk(root: string, sessionId: string): ContinuityState | null {
  const path = statePath(root, sessionId);
  if (!existsSync(path)) return null;
  try {
    return merge(emptyState(), JSON.parse(readFileSync(path, "utf-8")));
  } catch {
    return null;
  }
}

export function saveToDisk(root: string, sessionId: string, state: ContinuityState): void {
  try {
    const path = statePath(root, sessionId);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(state, null, 2) + "\n");
  } catch {
    // A read-only or missing workspace must never break the session.
  }
}

export function recordFact(state: ContinuityState, fact: string): boolean {
  const text = clamp(fact);
  if (text === "" || state.facts.includes(text)) return false;
  state.facts.push(text);
  if (state.facts.length > MAX_FACTS) state.facts.splice(0, state.facts.length - MAX_FACTS);
  return true;
}

export function recordLoop(state: ContinuityState, evidence: LoopEvidence): LoopEvidence {
  const existing = state.loops.find((candidate) => candidate.sig === evidence.sig);
  if (existing !== undefined) {
    existing.count = evidence.count;
    existing.detail = evidence.detail;
    return existing;
  }
  state.loops.push(evidence);
  if (state.loops.length > MAX_LOOPS) state.loops.shift();
  return evidence;
}

/** A request the extension made, and whether the runtime took it. */
export function recordRequest(state: ContinuityState, why: string, declined: boolean): void {
  state.requests.push(declined ? why + ":declined" : why);
  if (state.requests.length > MAX_REQUESTS) state.requests.splice(0, state.requests.length - MAX_REQUESTS);
}

export function recordIntervention(state: ContinuityState, evidence: LoopEvidence[]): void {
  state.interventions.push({
    turn: state.turns,
    escalation: state.escalation,
    kinds: evidence.map((item) => item.kind),
    sigs: evidence.map((item) => item.sig),
    counts: evidence.map((item) => item.count),
    outcome: "pending",
    turnsToOutcome: null,
    newPathsAfter: 0,
  });
  if (state.interventions.length > MAX_INTERVENTIONS) state.interventions.shift();
}

/**
 * Answers the open ledger rows. Progress is the only thing that counts as
 * "broke"; silence through the whole patience window counts as "failed".
 *
 * A repeated signature must not fail a row on its own: a stall's counter
 * climbs every quiet turn, so the row would close one turn after it opened and
 * no evidence could land. The window has to elapse.
 */
export function resolveInterventions(
  state: ContinuityState,
  progressed: boolean,
  patienceTurns: number,
  newPaths = 0,
): void {
  for (const record of state.interventions) {
    if (record.outcome !== "pending") continue;
    const elapsed = state.turns - record.turn;
    if (elapsed <= 0) continue;
    record.newPathsAfter += newPaths;
    if (progressed) {
      record.outcome = "broke";
      record.turnsToOutcome = elapsed;
      continue;
    }
    if (elapsed >= patienceTurns) {
      record.outcome = "failed";
      record.turnsToOutcome = elapsed;
    }
  }
}

/** Requests kept per session — enough to read a pattern, not a log. */
const MAX_REQUESTS = 32;

/** Progress retires the ladder: an intervention is only ever for a stuck session. */
export function resetEscalation(state: ContinuityState): void {
  state.escalation = 0;
  state.loops = [];
}

// ============================================================
// Helpers
// ============================================================

function statePath(root: string, sessionId: string): string {
  const safe = sessionId.replace(/[^\w.-]/g, "_") || "unknown";
  return join(root, ".omp", "state", safe + STATE_SUFFIX);
}

/** Field-by-field narrowing: a stored blob may predate any field here. */
function merge(base: ContinuityState, incoming: unknown): ContinuityState {
  if (incoming === null || typeof incoming !== "object") return base;
  return {
    v: 1,
    goal: readString(incoming, "goal") ?? base.goal,
    nextAction: readString(incoming, "nextAction") ?? base.nextAction,
    facts: readStrings(incoming, "facts")?.slice(-MAX_FACTS) ?? base.facts,
    banned: readStrings(incoming, "banned")?.slice(-MAX_LOOPS) ?? base.banned,
    loops: readLoops(incoming)?.slice(-MAX_LOOPS) ?? base.loops,
    interventions: readInterventions(incoming)?.slice(-MAX_INTERVENTIONS) ?? base.interventions,
    escalation: readNumber(incoming, "escalation") ?? base.escalation,
    turns: readNumber(incoming, "turns") ?? base.turns,
    toolCalls: readNumber(incoming, "toolCalls") ?? base.toolCalls,
    compactions: readNumber(incoming, "compactions") ?? base.compactions,
    recoveries: readNumber(incoming, "recoveries") ?? base.recoveries,
    // Omitting a field here silently deletes it on every restore, and the next
    // write throws on `undefined.push`.
    requests: readStrings(incoming, "requests")?.slice(-MAX_REQUESTS) ?? base.requests,
    lastUsage: readString(incoming, "lastUsage") ?? base.lastUsage,
    acceptance: readArray(incoming, "acceptance") ?? base.acceptance,
    deadlineMs: readNumber(incoming, "deadlineMs") ?? base.deadlineMs,
    agentDir: readString(incoming, "agentDir") ?? base.agentDir,
    startedAt: readNumber(incoming, "startedAt") ?? base.startedAt,
  };
}

function readString(source: object, key: string): string | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  return typeof value === "string" ? value : undefined;
}

function readNumber(source: object, key: string): number | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

/** Opaque rows kept as declared - predicates are rebuilt where they are used. */
function readArray(source: object, key: string): unknown[] | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  return Array.isArray(value) ? value : undefined;
}

function readStrings(source: object, key: string): string[] | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  if (!Array.isArray(value)) return undefined;
  return value.filter((item): item is string => typeof item === "string");
}

function readLoops(source: object): LoopEvidence[] | undefined {
  if (!("loops" in source)) return undefined;
  const value = Reflect.get(source, "loops");
  if (!Array.isArray(value)) return undefined;
  const loops: LoopEvidence[] = [];
  for (const item of value) {
    if (item === null || typeof item !== "object") continue;
    const sig = readString(item, "sig");
    const kind = readString(item, "kind");
    if (sig === undefined || !isLoopKind(kind)) continue;
    loops.push({
      sig,
      kind,
      count: readNumber(item, "count") ?? 1,
      detail: readString(item, "detail") ?? "",
    });
  }
  return loops;
}

function readInterventions(source: object): Intervention[] | undefined {
  if (!("interventions" in source)) return undefined;
  const value = Reflect.get(source, "interventions");
  if (!Array.isArray(value)) return undefined;
  const records: Intervention[] = [];
  for (const item of value) {
    if (item === null || typeof item !== "object") continue;
    const turn = readNumber(item, "turn");
    const outcome = readString(item, "outcome");
    if (turn === undefined || !isOutcome(outcome)) continue;
    records.push({
      turn,
      escalation: readNumber(item, "escalation") ?? 0,
      kinds: (readStrings(item, "kinds") ?? []).filter(isLoopKind),
      sigs: readStrings(item, "sigs") ?? [],
      counts: readNumbers(item, "counts") ?? [],
      outcome,
      turnsToOutcome: readNumber(item, "turnsToOutcome") ?? null,
      newPathsAfter: readNumber(item, "newPathsAfter") ?? 0,
    });
  }
  return records;
}

function readNumbers(source: object, key: string): number[] | undefined {
  if (!(key in source)) return undefined;
  const value = Reflect.get(source, key);
  if (!Array.isArray(value)) return undefined;
  return value.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
}

function isOutcome(value: string | undefined): value is InterventionOutcome {
  return value === "pending" || value === "broke" || value === "failed";
}

/**
 * Every kind, or a restore silently drops the rows it does not recognise:
 * `thrash` was missing here, so a resumed session lost exactly the evidence
 * that had made it intervene.
 */
function isLoopKind(value: string | undefined): value is LoopKind {
  return (
    value === "repeat" ||
    value === "oscillation" ||
    value === "errorLoop" ||
    value === "stall" ||
    value === "thrash" ||
    value === "blind"
  );
}

function clamp(text: string): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  return collapsed.length > MAX_TEXT ? collapsed.slice(0, MAX_TEXT) + "…" : collapsed;
}
