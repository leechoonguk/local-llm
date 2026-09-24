// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
import { resolveProjectRoot } from "./hook-project-root.ts";

/**
 * The harness's one way into the application database.
 *
 * One `psql -tAc` through the postgres container: no local client, no second
 * copy of the credentials, and compose's project scoping kept — a bare
 * `docker exec postgres` reaches whichever container in any project answers to
 * that name. `check-tooling` enforces the singularity, because two modules
 * spawning psql are two places to keep the container path and the credentials
 * correct in.
 *
 * Throws when the database cannot be reached, so a caller says *why* it
 * compared nothing instead of reporting a pass it never earned.
 */

const projectRoot = resolveProjectRoot();

/** Long enough for a container round trip, short enough not to stall a gate. */
const PSQL_TIMEOUT_MS = 30_000;

// ============================================================
// Functions
// ============================================================

/** The rows of a one-line query, blank lines dropped. */
export function queryDatabase(sql: string, timeoutMs: number = PSQL_TIMEOUT_MS): string[] {
  const env = readEnv(join(projectRoot, ".env"));
  const user = env.get("POSTGRES_USER");
  const database = env.get("POSTGRES_DB");
  if (user === undefined || database === undefined) {
    throw new Error("POSTGRES_USER / POSTGRES_DB missing from .env — cannot query the database");
  }
  const result = spawnSync(
    "docker",
    ["compose", "exec", "-T", "postgres", "psql", "-U", user, "-d", database, "-tAc", sql],
    { cwd: projectRoot, encoding: "utf-8", timeout: timeoutMs },
  );
  if (result.status !== 0) {
    const reason = String(result.stderr ?? "").trim().split("\n")[0];
    throw new Error(
      `postgres unreachable (${reason || "docker compose exec failed"}) — start it with make infra-up`,
    );
  }
  return String(result.stdout)
    .split("\n")
    .map((line: string) => line.trim())
    .filter((line: string) => line !== "");
}

/** The `.env` pairs, as docker compose reads them. */
function readEnv(path: string): Map<string, string> {
  const env = new Map<string, string>();
  if (!existsSync(path)) return env;
  for (const line of readFileSync(path, "utf-8").split("\n")) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (match === null) continue;
    env.set(match[1], match[2].replace(/^["']|["']$/g, ""));
  }
  return env;
}
