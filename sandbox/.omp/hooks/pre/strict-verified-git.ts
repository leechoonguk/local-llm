import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

const GIT_PUBLISH = /(?:^|[&|;()]\s*)(?:sudo\s+)?git(?:\s+-\S+(?:\s+\S+)?)*\s+(?:commit|push)\b/;
const GIT_COMMIT = /(?:^|[&|;()]\s*)(?:sudo\s+)?git(?:\s+-\S+(?:\s+\S+)?)*\s+commit\b/;
const VERIFY_ENV_KEYS = [
  "ENV",
  "DATABASE_URL",
  "REDIS_URL",
  "APP_NAME",
  "ADMIN_EMAIL",
  "ITEMS_PER_USER",
  "CORS_ORIGINS",
  "SECRET_KEY",
  "ACCESS_TOKEN_EXPIRE_MINUTES",
  "ALGORITHM",
  "INTEGRATION_TIMEOUT_SECONDS",
  "INTEGRATION_CONNECT_TIMEOUT_SECONDS",
  "INTEGRATION_MAX_RETRIES",
  "INTEGRATION_RETRY_BASE_SECONDS",
  "INTEGRATION_RETRY_MAX_SECONDS",
];

/**
 * Blocks OMP-mediated Git commits and pushes unless the current workspace passes
 * the root quality gate immediately before the Git command executes.
 *
 * `make verify` reads the **worktree**, so a commit is only covered by it when
 * the commit *is* the worktree: an unstaged change or an untracked file means
 * the verified tree and the committed tree are different trees, and the gate
 * proved nothing about the one being published. This session's own
 * `lib/hook-visibility.ts` was that case — untracked while 36 tracked hooks
 * imported it, so committing only the hooks would have published a tree that
 * cannot even type-check, with a green verify behind it.
 */
export default function strictVerifiedGit(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName?: string; input?: Record<string, unknown> }, ctx: { cwd: string }) => {
    if (event.toolName !== "bash") return;

    const command = String(event.input?.command ?? "");
    if (!GIT_PUBLISH.test(command)) return;

    // Cheap first: a mismatched index makes the 25s verify irrelevant anyway.
    if (GIT_COMMIT.test(command)) {
      const mismatch = describeUncommittedWork(ctx.cwd);
      if (mismatch !== null) return { block: true, reason: mismatch };
    }
    const projectRoot = existsSync(join(ctx.cwd, "backend", "app")) ? ctx.cwd : join(ctx.cwd, "..");
    const verifyEnv = { ...process.env };
    for (const key of VERIFY_ENV_KEYS) delete verifyEnv[key];

    const result = spawnSync("make", ["verify"], {
      cwd: projectRoot,
      env: verifyEnv,
      encoding: "utf-8",
      timeout: 10 * 60 * 1000,
    });
    if (result.status === 0) return;

    return {
      block: true,
      reason:
        `make verify failed (exit ${result.status ?? "unknown"}); ` +
        "Git commit/push is blocked until verification passes.",
    };
  });
}

/**
 * The reason string when the commit would not be the verified tree, or null.
 *
 * Partial staging is a legitimate workflow (the commit skill says to stage only
 * the approved scope), so the block names both ways out — stage the rest, or
 * move it out of the way — instead of forcing one of them.
 */
function describeUncommittedWork(cwd: string): string | null {
  const status = spawnSync("git", ["status", "--porcelain"], { cwd, encoding: "utf-8" });
  if (status.status !== 0) return null;

  const unstaged: string[] = [];
  const untracked: string[] = [];
  for (const line of String(status.stdout ?? "").split("\n")) {
    if (line.trim() === "") continue;
    const path = line.slice(3);
    if (line.startsWith("??")) untracked.push(path);
    else if (line[1] !== " ") unstaged.push(path);
  }
  if (unstaged.length === 0 && untracked.length === 0) return null;

  const sample = [...unstaged, ...untracked].slice(0, 5).join(", ");
  const more = unstaged.length + untracked.length - 5;
  return (
    `the commit would not be the verified tree: ${unstaged.length} unstaged change(s) and ` +
    `${untracked.length} untracked file(s) (${sample}${more > 0 ? `, +${more} more` : ""}). ` +
    "`make verify` reads the worktree, so an index that differs from it was never verified — " +
    "run `git add -A` to commit what was verified, or `git stash -k` to move the rest out first."
  );
}
