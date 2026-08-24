import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { relative, resolve } from "node:path";
import {
  isPushedMigration as isUpstreamMigration,
  listPushedMigrationsMutatedBy,
} from "../lib/backend-migration-policy.ts";

const cwd = process.cwd();
const projectRoot = existsSync(resolve(cwd, "backend", "app")) ? cwd : resolve(cwd, "..");

/**
 * Strict-Backend-Migrations Pre Hook
 *
 * Allows edits to unpushed migration revisions. A migration becomes immutable
 * once its path exists on the branch's configured Git upstream.
 *
 * Immutability is about the file, not the tool that reaches it. Measured: a
 * local model told to follow the seed-naming rule renamed two published
 * revisions with `mv`, which the write/edit guard never sees - a rename is not a
 * write. So shell and eval bodies are read for the same policy.
 */
export default function strictBackendMigrations(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    const toolName = String(event.toolName ?? "");

    if (toolName === "bash" || toolName === "eval") {
      const body = String(event.input.command ?? event.input.code ?? "");
      const pushed = listPushedMigrationsMutatedBy(body);
      if (pushed.length === 0) return;
      return {
        block: true,
        reason:
          "pushed migration is immutable, and a rename or delete is not an exception — " +
          pushed.join(", ") +
          ". Create a new revision instead; renaming a published revision changes what every " +
          "other checkout already applied.",
      };
    }

    if (toolName !== "write" && toolName !== "edit") return;

    const path = String(event.input.path ?? "");
    if (!isMigrationPath(path) || !isPushedMigration(path)) return;

    return {
      block: true,
      reason:
        "pushed migration is immutable — create a new revision for the correction. " +
        "Unpushed migration files remain editable.",
    };
  });
}

function isMigrationPath(path: string): boolean {
  return relative(projectRoot, resolve(projectRoot, path)).startsWith("backend/alembic/versions/");
}

function isPushedMigration(path: string): boolean {
  const relativePath = relative(projectRoot, resolve(projectRoot, path));
  return isUpstreamMigration(relativePath);
}
