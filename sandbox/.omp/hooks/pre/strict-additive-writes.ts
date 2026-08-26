/**
 * Strict-Additive-Writes Pre Hook
 *
 * An additive task must not wipe existing code. Measured failure class: asked
 * to ADD a domain, a local model rewrote a shared file and dropped lines that
 * other domains depended on (alembic/env.py lost the `user` model import —
 * recorded as a destructive regression). The write/edit path that loses the
 * most at once is a full-file `write` onto an existing source file; the shell
 * twin is a `>` truncation. Both are blocked with guidance toward targeted
 * edits — `edit` changes survive, wholesale rewrites forget.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { resolve } from "node:path";

const MIN_LINES = 12;        // files smaller than this are cheap to rewrite honestly
const RETAIN_FLOOR = 0.5;    // block when less than half of the existing lines survive

export default function strictAdditiveWrites(pi: any) {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    const toolName = String(event.toolName ?? "");

    if (toolName === "bash" || toolName === "eval") {
      const body = String(event.input.command ?? event.input.code ?? "");
      const m = body.match(/(?<![>\d&])>\s*([\w@./-]+\.(?:py|ts|tsx|js|mjs|md|yml|yaml|toml|json|http))\b/);
      if (!m) return;
      const abs = resolve(process.cwd(), m[1]);
      if (!existsSync(abs)) return;
      if (countLines(abs) < MIN_LINES) return;
      return {
        block: true,
        reason:
          `\`> ${m[1]}\` truncates an existing file — append with >>, or use the edit tool ` +
          "for targeted changes. An additive task must not wipe existing content.",
      };
    }

    if (toolName === "edit") {
      // Field shape measured from the runtime: {path, old_string, new_string}
      // or {path, edits: [{old_string, new_string}]}.
      const pairs: Array<{ old_string?: unknown; new_string?: unknown }> =
        Array.isArray((event.input as any).edits) ? (event.input as any).edits : [event.input as any];
      for (const pr of pairs) {
        const oldStr = String(pr.old_string ?? "");
        const newStr = String(pr.new_string ?? "");
        if (!oldStr) continue;
        // (a) Replacing an existing import line — the measured env.py class:
        // asked to ADD a model import, the model swapped the `User` line for
        // `Notice`. A replaced import is wiped code; add alongside instead.
        const oldImports = meaningfulLines(oldStr).filter((l: string) => /^(from\s+\S+\s+import\b|import\s+\S)/.test(l));
        const dropped = oldImports.filter((l: string) => !newStr.includes(l));
        const addsImport = /(^|\n)\s*(from\s+\S+\s+import\b|import\s+\S)/.test(newStr);
        if (dropped.length > 0 && addsImport) {
          return {
            block: true,
            reason:
              `this edit replaces an existing import (\`${String(dropped[0]).slice(0, 60)}\`) with a new one — ` +
              "an additive task adds its import alongside; existing imports register models/behavior " +
              "other code depends on. Keep the old line and add yours next to it.",
          };
        }
        // (b) Egregious deletion: a large block mostly vanishes.
        const oldLines = meaningfulLines(oldStr);
        if (oldLines.length >= 8) {
          const newSet = new Set(meaningfulLines(newStr));
          const retained = oldLines.filter((l: string) => newSet.has(l)).length / oldLines.length;
          if (retained < 0.3) {
            return {
              block: true,
              reason:
                `this edit deletes ~${Math.round((1 - retained) * 100)}% of a ${oldLines.length}-line block — ` +
                "an additive task must not wipe existing code; make a narrower edit that keeps unrelated lines.",
            };
          }
        }
      }
      return;
    }

    if (toolName !== "write") return;
    const path = String(event.input.path ?? "");
    if (!/\.(?:py|ts|tsx|js|mjs|yml|yaml|toml|json|http)$/.test(path)) return;
    const abs = resolve(process.cwd(), path);
    if (!existsSync(abs)) return;
    const oldLines = meaningfulLines(readFileSync(abs, "utf-8"));
    if (oldLines.length < MIN_LINES) return;
    const newSet = new Set(meaningfulLines(String(event.input.content ?? event.input.text ?? "")));
    const retained = oldLines.filter((l: string) => newSet.has(l)).length / oldLines.length;
    if (retained >= RETAIN_FLOOR) return;
    return {
      block: true,
      reason:
        `overwriting ${path} drops ~${Math.round((1 - retained) * 100)}% of its existing lines — ` +
        "the task adds code, it does not replace the file. Use the edit tool for targeted " +
        "changes, or include the existing content you mean to keep.",
    };
  });
}

function meaningfulLines(content: string): string[] {
  return content.split("\n").map((l: string) => l.trim()).filter((l: string) => l !== "");
}

function countLines(path: string): number {
  try { return meaningfulLines(readFileSync(path, "utf-8")).length; } catch { return 0; }
}
