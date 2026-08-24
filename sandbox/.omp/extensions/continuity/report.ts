/**
 * Continuity Report
 *
 * Reads every session's continuity state and answers the only question that can
 * move a threshold: **did the intervention break the loop?**
 *
 * A detector threshold is a guess until this table exists. Two readings matter:
 *
 *   - a kind whose interventions mostly end `failed` is either firing on
 *     something that is not a loop, or answering it with the wrong intervention;
 *   - a kind that always ends `broke` at a high loop count was probably
 *     detectable earlier — the threshold can come down.
 *
 * Run with `make continuity-report`. It is read-only: it opens
 * `.omp/state/*.continuity.json` and prints.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { STATE_SUFFIX } from "./state.ts";

// ============================================================
// Constants
// ============================================================

const cwd = process.cwd();
const stateDir = join(cwd, ".omp", "state");

/** Below this many resolved rows a rate is noise, not evidence. */
const MIN_SAMPLE = 3;

// ============================================================
// Types
// ============================================================

interface Row {
  kind: string;
  broke: number;
  failed: number;
  pending: number;
  countsAtFire: number[];
  turnsToBreak: number[];
  /** New files read after a failed intervention - research looks like a stall. */
  readsAfterFailure: number[];
  /** Resolved outcomes newest-session-first, for the current-behaviour cohort. */
  recent: Array<{ at: number; broke: boolean }>;
}

// ============================================================
// Functions
// ============================================================

export function report(): string[] {
  if (!existsSync(stateDir)) {
    return ["no continuity state yet — nothing has been recorded under .omp/state/"];
  }

  const rows = new Map<string, Row>();
  const requests = new Map<string, { made: number; declined: number }>();
  let sessions = 0;
  let interventions = 0;
  let probes = 0;
  let unlabelled = 0;

  // Newest session last: the cohort that describes current behaviour is built
  // from the end of this list, and a detector fixed yesterday is invisible in a
  // rate pooled over every version that ever ran.
  for (const file of byModified(readdirSync(stateDir))) {
    if (!file.endsWith(STATE_SUFFIX)) continue;
    const origin = readOrigin(join(stateDir, file));
    if (origin === "probe") {
      probes += 1;
      continue;
    }
    // A file written before this field existed cannot say whether a probe drove
    // it. Measured: the two surviving "repeat" samples were loop probes whose
    // prompt ordered the repetition, and they read as "the intervention never
    // works" — the wrong conclusion drawn from the wrong rows.
    if (origin === "unlabelled") {
      unlabelled += 1;
      continue;
    }
    const parsed = parse(join(stateDir, file));
    if (parsed === null) continue;
    sessions += 1;
    const at = modifiedAt(join(stateDir, file));
    for (const why of readRequests(join(stateDir, file))) {
      const declined = why.endsWith(":declined");
      const reason = declined ? why.slice(0, -":declined".length) : why;
      const tally = requests.get(reason) ?? { made: 0, declined: 0 };
      if (declined) tally.declined += 1;
      else tally.made += 1;
      requests.set(reason, tally);
    }
    for (const record of parsed) {
      interventions += 1;
      for (let index = 0; index < record.kinds.length; index++) {
        const row = rows.get(record.kinds[index]) ?? {
          kind: record.kinds[index],
          broke: 0,
          failed: 0,
          pending: 0,
          countsAtFire: [],
          turnsToBreak: [],
          readsAfterFailure: [],
          recent: [],
        };
        if (record.outcome === "broke") row.broke += 1;
        else if (record.outcome === "failed") row.failed += 1;
        else row.pending += 1;
        if (record.outcome === "broke" || record.outcome === "failed") {
          row.recent.push({ at, broke: record.outcome === "broke" });
        }
        const count = record.counts[index];
        if (typeof count === "number") row.countsAtFire.push(count);
        if (record.outcome === "broke" && record.turnsToOutcome !== null) {
          row.turnsToBreak.push(record.turnsToOutcome);
        }
        // A failed row that kept opening files was research, not a stuck
        // session: the signal was wrong, not the answer.
        if (record.outcome === "failed" && record.newPathsAfter !== null) {
          row.readsAfterFailure.push(record.newPathsAfter);
        }
        rows.set(row.kind, row);
      }
    }
  }

  const lines: string[] = [];
  lines.push(
    "sessions=" + String(sessions) + " interventions=" + String(interventions) +
      excluded(probes, unlabelled) + " (read-only)",
  );
  const empty = rows.size === 0;
  if (empty) {
    lines.push(
      unlabelled > 0 && sessions === 0
        ? "no labelled sessions yet — every sample predates the probe marker"
        : "no interventions recorded — the ladder has not fired yet",
    );
  }

  // A request this extension made is the other half of the evidence: a
  // threshold that never fires is as wrong as one that fires uselessly.
  lines.push("");
  lines.push(
    requests.size === 0
      ? "compaction requests: none — no threshold in this extension has fired yet"
      : "compaction requests: " +
          [...requests]
            .map(([reason, tally]) => reason + "=" + String(tally.made) + (tally.declined === 0 ? "" : " (" + String(tally.declined) + " declined)"))
            .join("  "),
  );

  if (empty) return lines;

  lines.push("");
  lines.push("kind          broke  failed  pending  break-rate  current     count@fire  turns→break  reads@failed  reading");
  for (const row of [...rows.values()].sort((left, right) => resolved(right) - resolved(left))) {
    const total = resolved(row);
    const rate = total === 0 ? "—" : String(Math.round((row.broke / total) * 100)) + "%";
    const now = cohort(row);
    lines.push(
      pad(row.kind, 13) +
        pad(String(row.broke), 7) +
        pad(String(row.failed), 8) +
        pad(String(row.pending), 9) +
        pad(rate, 12) +
        pad(now.label, 12) +
        pad(median(row.countsAtFire), 12) +
        pad(median(row.turnsToBreak), 13) +
        pad(readShare(row.readsAfterFailure), 14) +
        reading(row, now.broke, now.total),
    );
  }
  return lines;
}

// ============================================================
// Helpers
// ============================================================

/** State files oldest first, so the newest sessions land at the end of the walk. */
function byModified(files: string[]): string[] {
  return [...files].sort((left, right) => modifiedAt(join(stateDir, left)) - modifiedAt(join(stateDir, right)));
}

function modifiedAt(path: string): number {
  try {
    return statSync(path).mtimeMs;
  } catch {
    return 0;
  }
}

/**
 * The newest sessions that together carry MIN_SAMPLE resolved rows. The pooled
 * rate answers "how has this detector ever behaved" and keeps answering it long
 * after the detector changed: measured here, 30 pre-fix sessions read 14% and
 * the one session after the fix read 69%, which pooled to 32% and printed
 * "intervention rarely works" about code that no longer exists.
 */
function cohort(row: Row): { broke: number; total: number; label: string } {
  const sessions = [...new Set(row.recent.map((sample) => sample.at))].sort((left, right) => right - left);
  let broke = 0;
  let total = 0;
  let used = 0;
  for (const at of sessions) {
    used += 1;
    for (const sample of row.recent) {
      if (sample.at !== at) continue;
      total += 1;
      if (sample.broke) broke += 1;
    }
    if (total >= MIN_SAMPLE) break;
  }
  const label = total === 0 ? "—" : `${String(Math.round((broke / total) * 100))}% (${String(used)}s)`;
  return { broke, total, label };
}

/**
 * How many failed rows were still opening files. The share, not a median:
 * most rows are zero. A failed row with reads was research the detector
 * mislabelled; one without was really stuck.
 */
function readShare(values: number[]): string {
  if (values.length === 0) return "—";
  const reading = values.filter((value) => value > 0).length;
  return String(reading) + "/" + String(values.length);
}

/**
 * Where a sample came from: a probe drove its own behaviour, and a file written
 * before the marker existed cannot answer the question at all.
 */
function readOrigin(path: string): "session" | "probe" | "unlabelled" {
  try {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    if (raw === null || typeof raw !== "object") return "unlabelled";
    if (!("agentDir" in raw)) return "unlabelled";
    return String(Reflect.get(raw, "agentDir") ?? "") === "" ? "session" : "probe";
  } catch {
    return "unlabelled";
  }
}

/** The excluded counts, named so a reader knows why a table looks empty. */
function excluded(probes: number, unlabelled: number): string {
  const parts: string[] = [];
  if (probes > 0) parts.push(String(probes) + " probe");
  if (unlabelled > 0) parts.push(String(unlabelled) + " unlabelled");
  return parts.length === 0 ? "" : " (" + parts.join(", ") + " excluded)";
}

/** The reasons this extension asked the runtime to compact, per session file. */
function readRequests(path: string): string[] {
  try {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    if (raw === null || typeof raw !== "object") return [];
    const value = Reflect.get(raw, "requests");
    if (!Array.isArray(value)) return [];
    return value.filter((entry): entry is string => typeof entry === "string");
  } catch {
    return [];
  }
}

function parse(path: string): Intervention[] | null {
  try {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    if (raw === null || typeof raw !== "object" || !("interventions" in raw)) return null;
    const value = Reflect.get(raw, "interventions");
    if (!Array.isArray(value)) return null;
    const records: Intervention[] = [];
    for (const item of value) {
      if (item === null || typeof item !== "object") continue;
      const kinds = Reflect.get(item, "kinds");
      const counts = Reflect.get(item, "counts");
      const outcome = Reflect.get(item, "outcome");
      const turnsToOutcome = Reflect.get(item, "turnsToOutcome");
      const newPathsAfter = Reflect.get(item, "newPathsAfter");
      if (!Array.isArray(kinds) || typeof outcome !== "string") continue;
      records.push({
        kinds: kinds.filter((kind): kind is string => typeof kind === "string"),
        counts: Array.isArray(counts)
          ? counts.filter((count): count is number => typeof count === "number")
          : [],
        outcome,
        turnsToOutcome: typeof turnsToOutcome === "number" ? turnsToOutcome : null,
        newPathsAfter: typeof newPathsAfter === "number" ? newPathsAfter : null,
      });
    }
    return records;
  } catch {
    return null;
  }
}

interface Intervention {
  kinds: string[];
  counts: number[];
  outcome: string;
  turnsToOutcome: number | null;
  /** New files read after the intervention; absent in rows written before it existed. */
  newPathsAfter: number | null;
}

function resolved(row: Row): number {
  return row.broke + row.failed;
}

/** Judged on the current cohort: a stale rate is how a fixed detector stays condemned. */
function reading(row: Row, broke: number, total: number): string {
  if (total < MIN_SAMPLE) return "too few samples (" + String(total) + "/" + String(MIN_SAMPLE) + ")";
  const rate = broke / total;
  if (rate <= 0.34) return "intervention rarely works — wrong signal or wrong answer";
  if (rate >= 0.9 && median(row.countsAtFire) !== "—") {
    return "always works at count " + median(row.countsAtFire) + " — try firing earlier";
  }
  return "threshold looks reasonable";
}

function median(values: number[]): string {
  if (values.length === 0) return "—";
  const sorted = [...values].sort((left, right) => left - right);
  return String(sorted[Math.floor(sorted.length / 2)]);
}

function pad(text: string, width: number): string {
  return text.length >= width ? text + " " : text + " ".repeat(width - text.length);
}

// Direct execution (make continuity-report): print the table.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("report.ts")) {
  console.log("==> continuity-report");
  for (const line of report()) console.log("    " + line);
}
