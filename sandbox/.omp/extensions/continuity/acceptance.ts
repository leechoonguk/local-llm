/**
 * Acceptance Predicates
 *
 * A goal is only continued toward if "done" is falsifiable. These predicates are
 * the machine-checkable half of that: a command's exit status, a file's
 * existence, a pattern's presence. Anything a machine cannot decide is declared
 * `manual` and never counted as met — the same split the rules use for review
 * judgement.
 *
 * Two safety properties matter more than expressiveness here, because this runs
 * at settle time with no approval gate in front of it:
 *
 *   1. **Allowlisted commands only.** A predicate is a *verification*, so it must
 *      be a `make` target, a harness hook, or a read-only git query. Anything
 *      else is rejected, not run.
 *   2. **Bounded.** Each command gets a timeout and the whole pass gets a budget;
 *      when the budget is gone the remaining predicates are reported as skipped
 *      rather than silently treated as met.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { resolve } from "node:path";

// ============================================================
// Constants
// ============================================================

/** A verification command, not an arbitrary shell. Prefix match, exact list. */
const ALLOWED_COMMANDS = [
  "make ",
  "node .omp/hooks/",
  "git status --porcelain",
  "git diff --stat",
];

const DEFAULT_COMMAND_TIMEOUT_MS = 120_000;

/** Whole-pass ceiling: settle must not hang on verification. */
export const DEFAULT_BUDGET_MS = 180_000;

// ============================================================
// Types
// ============================================================

export type Predicate =
  | { kind: "shell"; cmd: string; expectExit?: number; timeoutMs?: number }
  | { kind: "file"; path: string; exists: boolean }
  | { kind: "grep"; path: string; pattern: string; want: boolean }
  | { kind: "manual"; text: string };

export interface Verdict {
  /** `null` when nothing was decided: manual, rejected, skipped, or unreadable. */
  met: boolean | null;
  label: string;
  detail: string;
}

// ============================================================
// Functions
// ============================================================

/** Runs every predicate within one budget and reports a verdict for each. */
export function evaluate(predicates: Predicate[], cwd: string, budgetMs = DEFAULT_BUDGET_MS): Verdict[] {
  const verdicts: Verdict[] = [];
  const deadline = Date.now() + budgetMs;

  for (const predicate of predicates) {
    if (Date.now() >= deadline) {
      verdicts.push({ met: null, label: label(predicate), detail: "skipped — verification budget spent" });
      continue;
    }
    verdicts.push(run(predicate, cwd, deadline));
  }
  return verdicts;
}

/** Met only when something was actually decided and every decision is true. */
export function allMet(verdicts: Verdict[]): boolean {
  return verdicts.some((verdict) => verdict.met === true) && !verdicts.some((verdict) => verdict.met === false);
}

export function render(verdicts: Verdict[]): string {
  return verdicts
    .map((verdict) => {
      const mark = verdict.met === true ? "met" : verdict.met === false ? "NOT met" : "undecided";
      return "  - [" + mark + "] " + verdict.label + " — " + verdict.detail;
    })
    .join("\n");
}

// ============================================================
// Helpers
// ============================================================

function run(predicate: Predicate, cwd: string, deadline: number): Verdict {
  if (predicate.kind === "manual") {
    return { met: null, label: "manual: " + predicate.text, detail: "a human decides this one" };
  }

  if (predicate.kind === "file") {
    const present = existsSync(resolve(cwd, predicate.path));
    return {
      met: present === predicate.exists,
      label: (predicate.exists ? "exists " : "absent ") + predicate.path,
      detail: present ? "file is present" : "file is absent",
    };
  }

  if (predicate.kind === "grep") {
    const path = resolve(cwd, predicate.path);
    if (!existsSync(path)) {
      return { met: null, label: "grep " + predicate.path, detail: "file does not exist" };
    }
    let found = false;
    try {
      found = new RegExp(predicate.pattern).test(readFileSync(path, "utf-8"));
    } catch (error: unknown) {
      return { met: null, label: "grep " + predicate.path, detail: "unreadable or bad pattern: " + String(error) };
    }
    return {
      met: found === predicate.want,
      label: (predicate.want ? "matches " : "does not match ") + predicate.pattern + " in " + predicate.path,
      detail: found ? "pattern present" : "pattern absent",
    };
  }

  const command = predicate.cmd.trim();
  if (!ALLOWED_COMMANDS.some((prefix) => command.startsWith(prefix))) {
    return {
      met: null,
      label: "shell " + command.slice(0, 60),
      detail: "rejected — acceptance runs unattended, so only " + ALLOWED_COMMANDS.join(", ") + " are allowed",
    };
  }

  const remaining = deadline - Date.now();
  const timeout = Math.max(1_000, Math.min(predicate.timeoutMs ?? DEFAULT_COMMAND_TIMEOUT_MS, remaining));
  const expected = predicate.expectExit ?? 0;
  const result = spawnSync(command, { cwd, shell: true, encoding: "utf-8", timeout });
  if (result.error !== undefined && result.error !== null) {
    return { met: null, label: "shell " + command, detail: "could not run: " + String(result.error) };
  }
  return {
    met: result.status === expected,
    label: "shell " + command,
    detail: "exit " + String(result.status) + " (expected " + expected + ")",
  };
}

function label(predicate: Predicate): string {
  if (predicate.kind === "shell") return "shell " + predicate.cmd.slice(0, 60);
  if (predicate.kind === "file") return (predicate.exists ? "exists " : "absent ") + predicate.path;
  if (predicate.kind === "grep") return "grep " + predicate.pattern + " in " + predicate.path;
  return "manual: " + predicate.text;
}
