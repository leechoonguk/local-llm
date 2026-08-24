// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";

/**
 * ORM ↔ DB sync check — alembic check (backend-migrations.md).
 *
 * Runs `alembic check` (autogenerate diff) and reports drift:
 *   - ORM drift (model changed, migration missing) → "New upgrade operations"
 *   - DB drift (schema changed outside migrations) → also detected
 *   - DB unreachable (infra down) → skipped silently, never blocks offline work
 *
 * Pure validation — no side effects. Called by the check-backend-domain
 * orchestrator.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

/** Last schema fingerprint and its verdict — reused until a model or migration changes. */
let lastFingerprint = "";
let lastIssues: string[] = [];

/**
 * `alembic check` is a database round trip: it measured 760ms on **every**
 * mutating tool result, whether or not anything schema-shaped had changed. The
 * answer can only change when a model or a migration changes, so the run is
 * gated on a fingerprint of those two directories.
 */
/**
 * Why the comparison did not run, when it did not run. `alembic check` needs a
 * live database; when it cannot reach one the hook must say so instead of
 * printing "in sync", which is a claim about a comparison that never happened.
 * Measured: with `DATABASE_URL` pointing at an unresolvable host, a real added
 * column was reported as PASS.
 */
export let lastSkipReason: string | null = null;

export function checkOrmDbSync(): string[] {
  const backendDir = join(projectRoot, "backend");
  const alembicBin = join(backendDir, ".venv", "bin", "alembic");
  if (!existsSync(alembicBin)) {
    lastSkipReason = "alembic is not installed (run make -C backend install)";
    return [];
  }

  const fingerprint = schemaFingerprint(backendDir);
  if (fingerprint === lastFingerprint) return lastIssues;
  lastSkipReason = null;

  lastFingerprint = fingerprint;
  lastIssues = runAlembicCheck(alembicBin, backendDir);
  return lastIssues;
}

function runAlembicCheck(alembicBin: string, backendDir: string): string[] {
  try {
    const result = spawnSync(alembicBin, ["check"], {
      cwd: backendDir,
      env: process.env,
      encoding: "utf-8",
      timeout: 30_000,
    });
    const output = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
    if (result.status !== 0 && output.includes("New upgrade operations detected")) {
      return [
        "ORM/DB out of sync — run 'make migrate-gen m=\"...\"' then 'make migrate' " +
          "(alembic check: " + output.split("\n").find((l) => l.includes("New upgrade operations"))?.trim() + ")",
      ];
    }
    // A database behind the files is not drift, but it is not nothing either:
    // measured on the local-model integration run, the agent wrote two seed
    // revisions, never applied them, and the whole gate still passed — the
    // seeded rows its own `.http` file and fixture describe did not exist. The
    // condition is cheap to clear (`make -C backend migrate`), so it is an
    // issue, not a silence.
    if (result.status !== 0 && output.includes("Target database is not up to date")) {
      return ["the database is behind the migrations — run 'make -C backend migrate'"];
    }
    // The reverse (files behind the database) is somebody else's branch, not
    // this tree's problem: stay dormant.
    if (result.status !== 0 && output.includes("Can't locate revision")) {
      lastSkipReason = "the database is ahead of this tree's migrations";
      return [];
    }
    if (result.status === 0) return [];

    // Anything else non-zero is infra, not drift: offline work must not be
    // blocked — but a gate that compared nothing may not report a pass, so the
    // reason is recorded and the CLI prints it as dormant.
    lastSkipReason = alembicFailure(output);
    return [];
  } catch (error: unknown) {
    lastSkipReason = `alembic check could not run (${String(error).slice(0, 80)})`;
  }
  return [];
}

/** The one line of alembic's traceback that names the cause. */
function alembicFailure(output: string): string {
  const lines = output.split("\n").map((line) => line.trim()).filter(Boolean);
  const named = lines.reverse().find((line) =>
    /gaierror|Connection refused|could not connect|password authentication|does not exist|timeout/i.test(line),
  );
  return named === undefined
    ? "the database is unreachable"
    : `the database is unreachable (${named.slice(0, 90)})`;
}

/**
 * Size+mtime of every model and migration. Nothing else can change the
 * autogenerate diff, so an identical fingerprint means an identical answer.
 */
function schemaFingerprint(backendDir: string): string {
  const roots = [join(backendDir, "app", "models"), join(backendDir, "alembic", "versions")];
  const parts: string[] = [];
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const file of readdirSync(root).sort()) {
      if (!file.endsWith(".py")) continue;
      const stat = statSync(join(root, file));
      parts.push(`${file}:${stat.size}:${stat.mtimeMs}`);
    }
  }
  return parts.join("|");
}
