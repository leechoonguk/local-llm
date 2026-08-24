/**
 * Loop Detectors
 *
 * Five mechanical signals, no model in the path. Each one answers "is this
 * session repeating itself?" from data the runtime already emits, and each
 * returns evidence keyed by a stable signature so a second sighting escalates
 * instead of re-firing.
 *
 * Normalization is the whole trick: a uuid, a timestamp or an absolute prefix
 * makes two identical attempts look different, and then nothing is ever a loop.
 */
import type { LoopEvidence } from "./state.ts";

// ============================================================
// Constants
// ============================================================

/** How many recent calls a repetition is judged against. */
const WINDOW = 24;

/** Identical attempts before it stops being a coincidence. */
const REPEAT_THRESHOLD = 3;

/** ABAB cycles before oscillation is called. */
const OSCILLATION_CYCLES = 2;

/** Turns with no file change, no new signature and no new fact. */
const STALL_TURNS = 3;

/**
 * Edits to one file with no check run in between. Editing twice while thinking
 * is normal; the third rewrite of the same file without ever asking whether the
 * first two worked is guessing, and the answer is one command away.
 */
const THRASH_EDITS = 3;

const VOLATILE = [
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/g,
  /\b\d{10,}\b/g,
  /\b\d{4}-\d{2}-\d{2}T[\d:.]+Z?\b/g,
];

// ============================================================
// Types
// ============================================================

export interface CallRecord {
  sig: string;
  tool: string;
  error?: string;
}

export interface DetectorInput {
  calls: CallRecord[];
  turnsWithoutProgress: number;
  /** Per-file successful edits since the last verifying command. */
  unverifiedEdits?: Array<{ path: string; count: number }>;
}

// ============================================================
// Functions
// ============================================================

/**
 * A tool call reduced to "the same attempt". The project root, uuids and
 * timestamps are stripped, keys are sorted, and long values are cut — two runs
 * of the same search must hash identically or repetition is invisible.
 */
export function signature(tool: string, input: Record<string, unknown>, root: string): string {
  const parts: string[] = [];
  for (const key of Object.keys(input).sort()) {
    const raw = input[key];
    if (raw === undefined || typeof raw === "function") continue;
    let text = typeof raw === "string" ? raw : JSON.stringify(raw) ?? "";
    text = text.split(root).join("");
    for (const pattern of VOLATILE) text = text.replace(pattern, "*");
    parts.push(key + "=" + text.slice(0, 120));
  }
  return tool + "(" + parts.join("&") + ")";
}

/** Every detector, in the order a reader should think about them. */
export function detect(input: DetectorInput): LoopEvidence[] {
  const recent = input.calls.slice(-WINDOW);
  const found: LoopEvidence[] = [];

  const counts = new Map<string, number>();
  for (const call of recent) counts.set(call.sig, (counts.get(call.sig) ?? 0) + 1);
  for (const [sig, count] of counts) {
    if (count < REPEAT_THRESHOLD) continue;
    found.push({ sig, kind: "repeat", count, detail: "identical call " + count + "x in the last " + recent.length });
  }

  const oscillation = findOscillation(recent.map((call) => call.sig));
  if (oscillation !== null) found.push(oscillation);

  const errors = new Map<string, number>();
  for (const call of recent) {
    if (call.error === undefined) continue;
    const key = call.tool + " :: " + call.error.slice(0, 120);
    errors.set(key, (errors.get(key) ?? 0) + 1);
  }
  for (const [key, count] of errors) {
    if (count < REPEAT_THRESHOLD) continue;
    found.push({ sig: "err:" + key, kind: "errorLoop", count, detail: "same failure " + count + "x: " + key });
  }

  for (const edit of input.unverifiedEdits ?? []) {
    if (edit.count < THRASH_EDITS) continue;
    found.push({
      sig: "thrash:" + edit.path,
      kind: "thrash",
      count: edit.count,
      detail: edit.count + " edits to " + edit.path + " with no check run in between",
    });
  }

  if (input.turnsWithoutProgress >= STALL_TURNS) {
    found.push({
      sig: "stall",
      kind: "stall",
      count: input.turnsWithoutProgress,
      detail: input.turnsWithoutProgress + " turns with no file change and no new finding",
    });
  }

  return found;
}

// ============================================================
// Helpers
// ============================================================

/**
 * The files a mutating call touched. `write`/`ast_edit` name them as arguments;
 * `edit` carries them as `[path#TAG]` section headers inside its body, so a
 * thrash on a hashline edit is invisible without parsing them out.
 */
/**
 * Paths a call read. Counted to tell research from a stall: a session reading
 * files it has not seen is learning, and only the reader knows that - the
 * write-side signal cannot.
 */
export function readPaths(tool: string, input?: Record<string, unknown>): string[] {
  if (input === undefined) return [];
  if (tool !== "read" && tool !== "grep" && tool !== "glob") return [];
  const single = input.path;
  if (typeof single !== "string") return [];
  // A selector or a glob is still one target; the range is not a new file.
  return [single.split(":")[0] ?? single];
}

export function touchedPaths(tool: string, input?: Record<string, unknown>): string[] {
  if (input === undefined) return [];
  if (tool === "write") {
    const path = input.path;
    return typeof path === "string" ? [path] : [];
  }
  if (tool === "ast_edit") {
    const paths = input.paths;
    return Array.isArray(paths) ? paths.filter((entry): entry is string => typeof entry === "string") : [];
  }
  if (tool === "edit") {
    const body = input.input;
    if (typeof body !== "string") return [];
    return [...body.matchAll(/^\[([^\]#]+)#[0-9A-Fa-f]{4}\]$/gm)].map((match) => match[1]);
  }
  // An `eval` cell that calls writeFileSync is an edit under another name — the
  // path it names is the only thing that distinguishes it from a computation.
  if (tool === "eval") {
    const code = input.code;
    if (typeof code !== "string") return [];
    const named = new Set<string>();
    for (const match of code.matchAll(/(?:writeFileSync|appendFileSync|renameSync)\(\s*["'`]([^"'`\n]+)/g)) {
      named.add(match[1]);
    }
    return [...named];
  }
  return [];
}

/** ABAB…: two alternating attempts are a loop the repeat counter can miss. */
function findOscillation(signatures: string[]): LoopEvidence | null {
  if (signatures.length < OSCILLATION_CYCLES * 2 + 2) return null;
  const tail = signatures.slice(-(OSCILLATION_CYCLES * 2 + 2));
  const a = tail[0];
  const b = tail[1];
  if (a === b) return null;
  for (let index = 0; index < tail.length; index++) {
    if (tail[index] !== (index % 2 === 0 ? a : b)) return null;
  }
  return {
    sig: "osc:" + a + "|" + b,
    kind: "oscillation",
    count: OSCILLATION_CYCLES,
    detail: "alternating between two attempts: " + a.slice(0, 60) + " <-> " + b.slice(0, 60),
  };
}
