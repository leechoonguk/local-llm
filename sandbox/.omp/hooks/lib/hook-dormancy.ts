/**
 * Dormancy reporting — shared by feature-gated post hooks.
 *
 * Seven hooks (rate-limit, file-upload, sse, api-keys, background-tasks,
 * audit-log, ownership) only assert something when the feature exists in the
 * app. They printed the same `PASS: ... standard valid` whether the code was
 * compliant or simply absent — so "34 checks passed" read as 34 guarded
 * invariants when 7 of them were guarding nothing. Measured, not assumed.
 *
 * A hook records why it is dormant and returns no issues; the CLI banner and the
 * warning path then say so. Two states, two different sentences.
 */

const reasons = new Map<string, string>();

/**
 * Records why a hook has nothing to assert and returns the empty issue list, so
 * a hook body reads `return dormant("check-backend-sse", "no SSE endpoint")`.
 */
export function dormant(hookName: string, reason: string): string[] {
  reasons.set(hookName, reason);
  return [];
}

/** The recorded reason, or null when the hook actually checked something. */
export function dormancyReason(hookName: string): string | null {
  return reasons.get(hookName) ?? null;
}

/** `PASS` line for a CLI run: compliant and dormant must not look alike. */
export function passLine(hookName: string, compliantMessage: string): string {
  const reason = reasons.get(hookName);
  return reason === null || reason === undefined
    ? `    PASS: ${compliantMessage}`
    : `    PASS: ${compliantMessage} (dormant — ${reason})`;
}
