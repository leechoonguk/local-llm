/**
 * Model Profile
 *
 * A small model does not fail at the context limit; it degrades well before it —
 * instructions from early in the window stop being followed, and the loop
 * detectors start firing on a model that is simply no longer reading its own
 * history. Waiting for OMP's threshold is therefore too late for a local 7-14B
 * model and exactly right for a frontier one.
 *
 * Reporting only. Compacting ahead of OMP from this signal was measured and
 * removed (see the note above the constants in `index.ts`); what the profile
 * still buys is a one-line answer to "how full was the window when that
 * happened", derived from the live model so `/model` needs no configuration.
 */

// ============================================================
// Constants
// ============================================================

/** Below this window a model is treated as small. 128k local models sit here. */
const SMALL_WINDOW_TOKENS = 200_000;

// ============================================================
// Types
// ============================================================

export interface Profile {
  name: "small" | "standard";
  detail: string;
}

// ============================================================
// Functions
// ============================================================

export function profileFor(model: unknown): Profile {
  const window = windowOf(model);
  if (window !== null && window < SMALL_WINDOW_TOKENS) {
    return { name: "small", detail: "window " + window + " tokens" };
  }
  return {
    name: "standard",
    detail: window === null ? "window unknown" : "window " + window + " tokens",
  };
}

/** Percent of the window in use, or null when the runtime cannot say. */
export function usagePercent(usage: unknown): number | null {
  const record = (usage ?? {}) as Record<string, unknown>;
  for (const key of ["percentage", "percent", "usedPercent"]) {
    const value = Number(record[key]);
    if (Number.isFinite(value)) return value;
  }
  const tokens = Number(record.tokens ?? record.used);
  const window = Number(record.contextWindow ?? record.window ?? record.max);
  if (Number.isFinite(tokens) && Number.isFinite(window) && window > 0) {
    return (tokens / window) * 100;
  }
  return null;
}

/** Absolute tokens in context, or null when the runtime cannot say. */
export function usageTokens(usage: unknown): number | null {
  if (usage === null || typeof usage !== "object") return null;
  for (const key of ["tokens", "used", "contextTokens"]) {
    if (!(key in usage)) continue;
    const value = Reflect.get(usage, key);
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

// ============================================================
// Helpers
// ============================================================

function windowOf(model: unknown): number | null {
  const record = (model ?? {}) as Record<string, unknown>;
  for (const key of ["contextWindow", "context_window", "maxContextTokens", "contextLength"]) {
    const value = Number(record[key]);
    if (Number.isFinite(value) && value > 0) return value;
  }
  return null;
}
