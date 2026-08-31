/**
 * Runs the gate twice and fails unless both runs pass.
 *
 * A flaky check passes once. Measured in this repo: `test_decode_tampered_token`
 * overwrote the last two base64url characters of a signature, and those carry only
 * two significant bits — occasionally the tampered token decoded to the same bytes
 * and verified, so `make verify` failed on the first run and passed on the second.
 * A single green run cannot tell that apart from a deterministic pass.
 *
 * Not the default gate: two full runs cost twice the wall clock, and the every-edit
 * feedback loop is worth more than the certainty on every save. This is the target
 * a publish path calls, where the cost is paid once and the certainty matters.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { dirname, join } from "node:path";
// @ts-expect-error — Node builtin, not project-compiled
import { fileURLToPath } from "node:url";

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

const RUNS = 2;

function runGate(attempt: number): boolean {
  console.log(`==> verify run ${attempt}/${RUNS}`);
  const result = spawnSync("make", ["verify"], {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    encoding: "utf-8",
  });
  const output = `${result.stdout ?? ""}${result.stderr ?? ""}`;
  if (result.status === 0) {
    const passes = output.split("\n").filter((line: string) => line.includes("PASS")).length;
    console.log(`    PASS (${passes} checks)`);
    return true;
  }
  // Only the failing lines: two full gate logs would bury the one that moved.
  for (const line of output.split("\n").filter((line: string) => /FAIL|Error|error/.test(line))) {
    console.log(`    ${line.trim()}`);
  }
  return false;
}

let allPassed = true;
for (let attempt = 1; attempt <= RUNS; attempt += 1) {
  if (!runGate(attempt)) {
    allPassed = false;
    break;
  }
}

if (allPassed) {
  console.log(`==> verify-twice\n    PASS: the gate passed ${RUNS} consecutive runs`);
  process.exit(0);
}

console.log("==> verify-twice\n    FAIL: a run did not pass — a check that fails once is either broken or flaky, and both block");
process.exit(1);
