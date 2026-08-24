/**
 * Goal Card and Mechanical Compaction
 *
 * Two renderers, both deterministic:
 *
 *   - `renderGoalCard` is what survives every context rewrite. It is injected as
 *     compaction context, so the goal, the verified facts and the single next
 *     action re-enter the transcript verbatim instead of being re-summarized by a
 *     model that may be small, busy, or unavailable.
 *   - `mechanicalSummary` is the fallback when compaction itself fails. OMP
 *     reports the failure through `auto_compaction_end` (`result: undefined`,
 *     `errorMessage` set); a session that cannot compact cannot continue, so this
 *     builds a compaction result from the data the preparation already carries —
 *     no summarizer model, no network, no vision requirement.
 *
 * The preparation payload comes from the runtime, so it is read through a guard
 * (`readPreparation`) rather than asserted: a payload this code cannot recognise
 * must disable the fallback, not produce a malformed compaction entry.
 */
import type { ContinuityState } from "./state.ts";

// ============================================================
// Constants
// ============================================================

/** Bounded so a fallback summary can never itself overflow the window. */
const MAX_FACTS = 12;
const MAX_TOOLS = 12;
const MAX_FILES = 20;
const MAX_PREVIOUS = 1200;

// ============================================================
// Types
// ============================================================

export interface Preparation {
  firstKeptEntryId: string;
  tokensBefore: number;
  messagesToSummarize: unknown[];
  previousSummary?: string;
  readFiles: string[];
  modifiedFiles: string[];
}

export interface MechanicalCompaction {
  summary: string;
  shortSummary: string;
  firstKeptEntryId: string;
  tokensBefore: number;
  preserveData: Record<string, unknown>;
}

// ============================================================
// Functions
// ============================================================

/** The block that must never be paraphrased away. */
export function renderGoalCard(state: ContinuityState): string {
  const lines: string[] = ["<continuity>"];
  lines.push("goal: " + (state.goal === "" ? "(not declared)" : state.goal));
  lines.push("next-action: " + (state.nextAction === "" ? "(not declared)" : state.nextAction));
  if (state.facts.length > 0) {
    lines.push("verified:");
    for (const fact of state.facts.slice(-MAX_FACTS)) lines.push("  - " + fact);
  }
  if (state.banned.length > 0) {
    lines.push("exhausted (do not repeat):");
    for (const sig of state.banned) lines.push("  - " + sig);
  }
  lines.push(
    "counters: turns=" + String(state.turns) +
      " toolCalls=" + String(state.toolCalls) +
      " compactions=" + String(state.compactions) +
      " recovered=" + String(state.recoveries),
  );
  lines.push("</continuity>");
  return lines.join("\n");
}

/**
 * Reads the runtime's compaction preparation, or returns null when it does not
 * carry the two fields a compaction entry cannot be built without.
 */
export function readPreparation(raw: unknown): Preparation | null {
  if (raw === null || typeof raw !== "object") return null;
  const firstKeptEntryId = "firstKeptEntryId" in raw ? Reflect.get(raw, "firstKeptEntryId") : undefined;
  const tokensBefore = "tokensBefore" in raw ? Reflect.get(raw, "tokensBefore") : undefined;
  if (typeof firstKeptEntryId !== "string" || typeof tokensBefore !== "number") return null;

  const messages = "messagesToSummarize" in raw ? Reflect.get(raw, "messagesToSummarize") : undefined;
  const previous = "previousSummary" in raw ? Reflect.get(raw, "previousSummary") : undefined;
  const fileOps = "fileOps" in raw ? Reflect.get(raw, "fileOps") : undefined;

  return {
    firstKeptEntryId,
    tokensBefore,
    messagesToSummarize: Array.isArray(messages) ? messages : [],
    previousSummary: typeof previous === "string" ? previous : undefined,
    readFiles: readPaths(fileOps, "readFiles"),
    modifiedFiles: readPaths(fileOps, "modifiedFiles"),
  };
}

/**
 * A summary built from facts, not prose: the goal card, the file operations the
 * discarded window performed, its tool histogram, and the unresolved errors. A
 * bounded head of the previous summary is carried so iterative continuity holds
 * across repeated fallbacks.
 */
export function mechanicalSummary(
  preparation: Preparation,
  state: ContinuityState,
  reason: string,
): MechanicalCompaction {
  const tools = toolHistogram(preparation.messagesToSummarize);
  const errors = errorLines(preparation.messagesToSummarize);

  const lines: string[] = [];
  lines.push("# Mechanical compaction (" + reason + ")");
  lines.push("");
  lines.push("The summarizer did not produce a summary for this pass, so this");
  lines.push("record was assembled from session data. It is complete about what");
  lines.push("happened and silent about intent — treat the goal card as the brief.");
  lines.push("");
  lines.push(renderGoalCard(state));
  lines.push("");
  if (tools.length > 0) {
    lines.push("## Work in the discarded window");
    for (const entry of tools.slice(0, MAX_TOOLS)) lines.push("- " + entry);
    lines.push("");
  }
  const files = filesSection(preparation);
  if (files.length > 0) {
    lines.push("## Files");
    for (const line of files) lines.push(line);
    lines.push("");
  }
  if (errors.length > 0) {
    lines.push("## Unresolved failures");
    for (const line of errors) lines.push("- " + line);
    lines.push("");
  }
  if (preparation.previousSummary !== undefined && preparation.previousSummary !== "") {
    lines.push("## Earlier summary (carried forward)");
    lines.push(preparation.previousSummary.slice(0, MAX_PREVIOUS));
  }

  return {
    summary: lines.join("\n"),
    shortSummary: "mechanical compaction — " + reason,
    firstKeptEntryId: preparation.firstKeptEntryId,
    tokensBefore: preparation.tokensBefore,
    preserveData: { continuity: state, mechanical: { reason, at: new Date().toISOString() } },
  };
}

// ============================================================
// Helpers
// ============================================================

function readPaths(fileOps: unknown, key: string): string[] {
  if (fileOps === null || typeof fileOps !== "object" || !(key in fileOps)) return [];
  const value = Reflect.get(fileOps, key);
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function toolHistogram(messages: unknown[]): string[] {
  const counts = new Map<string, number>();
  for (const message of messages) {
    for (const chunk of contentOf(message)) {
      if (chunk === null || typeof chunk !== "object") continue;
      const type = "type" in chunk ? Reflect.get(chunk, "type") : undefined;
      const name = "name" in chunk ? Reflect.get(chunk, "name") : undefined;
      if (type !== "toolCall" || typeof name !== "string") continue;
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .map(([name, count]) => name + " x" + String(count));
}

function errorLines(messages: unknown[]): string[] {
  const seen = new Set<string>();
  for (const message of messages) {
    if (message === null || typeof message !== "object") continue;
    const role = "role" in message ? Reflect.get(message, "role") : undefined;
    const isError = "isError" in message ? Reflect.get(message, "isError") : undefined;
    if (role !== "toolResult" || isError !== true) continue;
    for (const chunk of contentOf(message)) {
      if (chunk === null || typeof chunk !== "object") continue;
      const type = "type" in chunk ? Reflect.get(chunk, "type") : undefined;
      const text = "text" in chunk ? Reflect.get(chunk, "text") : undefined;
      if (type !== "text" || typeof text !== "string") continue;
      seen.add(text.replace(/\s+/g, " ").trim().slice(0, 160));
    }
  }
  return [...seen].slice(0, MAX_TOOLS);
}

function contentOf(message: unknown): unknown[] {
  if (message === null || typeof message !== "object" || !("content" in message)) return [];
  const content = Reflect.get(message, "content");
  return Array.isArray(content) ? content : [];
}

function filesSection(preparation: Preparation): string[] {
  const modified = new Set(preparation.modifiedFiles);
  const lines: string[] = [];
  for (const path of modified) lines.push(path + " (Write)");
  for (const path of preparation.readFiles) {
    if (modified.has(path)) continue;
    lines.push(path + " (Read)");
  }
  return lines.slice(0, MAX_FILES);
}
