import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { execFileSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Ast-Rules Post Hook
 *
 * Proves the rules that own the structural invariants actually fire
 * (omp-ast-rules.md). A rule is a claim; without a case that violates it, the
 * claim is untested — an anchored regex or a wrong `kind` silently matches
 * nothing and `make verify` stays green.
 *
 * Three checks:
 *   1. every rule under `.omp/ast-grep/rules/` has a test file in
 *      `.omp/ast-grep/tests/` declaring its id
 *   2. `ast-grep test` passes: each `invalid:` case must match, each `valid:`
 *      case must not
 *   3. ast-grep is available at all — a missing binary means none of the rules
 *      ran, which is a failure, not a pass
 */

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
  execPath: string;
};

// ============================================================
// Constants
// ============================================================

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const ompDir = join(projectRoot, ".omp");
const rulesRoot = join(ompDir, "ast-grep", "rules");
const testsRoot = join(ompDir, "ast-grep", "tests");
const sgConfig = join(ompDir, "sgconfig.yml");

const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

const AST_GREP_CANDIDATES = [
  join(projectRoot, "frontend", "node_modules", ".bin", "ast-grep"),
  "ast-grep",
];

const RULE_ID = /^id:\s*(\S+)/m;
const TEST_TIMEOUT_MS = 60_000;

// ============================================================
// Functions
// ============================================================

export default function checkAstRules(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-ast-rules", event, () => {
    // Read-only tools never change files — running the check after them wastes context.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/", "frontend/", ".omp/ast-grep"])) return;

    const issues = checkAstRulesSync();
    if (issues.length === 0) {
      resetSuppression("check-ast-rules");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-ast-rules",
      issues,
      "make check-ast-rules",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-ast-rules") };
  }));
}

export function checkAstRulesSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(rulesRoot)) return issues;
  if (!existsSync(sgConfig)) {
    issues.push(".omp/sgconfig.yml is missing — the rule set cannot be tested");
    return issues;
  }

  issues.push(...checkEveryRuleHasATest());
  issues.push(...checkRuleRationale());
  issues.push(...checkTestFilenames());
  issues.push(...runRuleTests());
  return issues;
}

/** A rule without a violating case is an assertion nobody has ever seen fail. */
function checkEveryRuleHasATest(): string[] {
  const issues: string[] = [];
  const tested = new Set<string>();
  if (existsSync(testsRoot)) {
    for (const file of readdirSync(testsRoot)) {
      if (!file.endsWith(".yml")) continue;
      const id = RULE_ID.exec(readFileSync(join(testsRoot, file), "utf-8"));
      if (id !== null) tested.add(id[1]);
    }
  }

  for (const scope of readdirSync(rulesRoot, { withFileTypes: true })) {
    if (!scope.isDirectory()) continue;
    for (const file of readdirSync(join(rulesRoot, scope.name))) {
      if (!file.endsWith(".yml")) continue;
      const source = readFileSync(join(rulesRoot, scope.name, file), "utf-8");
      const id = RULE_ID.exec(source);
      if (id === null) {
        issues.push(`ast-grep/rules/${scope.name}/${file}: no \`id:\` — it cannot be tested or reported`);
        continue;
      }
      if (!tested.has(id[1])) {
        issues.push(
          `ast-grep/rules/${scope.name}/${file}: no test case in .omp/ast-grep/tests/ — add ` +
            `${id[1]} with a valid: and an invalid: snippet, or the rule may match nothing`,
        );
      }
    }
  }
  return issues;
}

/**
 * A structural rule reads as an assertion with no argument: the pattern says
 * *what* is rejected and never *why*. The leading comment is where the reason
 * lives, so the next reader can tell a real invariant from someone's taste.
 */
function checkRuleRationale(): string[] {
  const issues: string[] = [];
  for (const scope of readdirSync(rulesRoot, { withFileTypes: true })) {
    if (!scope.isDirectory()) continue;
    for (const file of readdirSync(join(rulesRoot, scope.name))) {
      if (!file.endsWith(".yml")) continue;
      const source = readFileSync(join(rulesRoot, scope.name, file), "utf-8");
      const head = source.split(/^rule:/m)[0];
      if (!/^#/m.test(head)) {
        issues.push(
          `ast-grep/rules/${scope.name}/${file}: no \`#\` comment above \`rule:\` — state why the ` +
            "rule exists, since the pattern alone cannot say it",
        );
      }
    }
  }
  return issues;
}

/**
 * The test file is found by its `id:`, so a mismatched name still passes. It is
 * read by a human looking for one rule's proof, though, and a name that does
 * not point back at the rule turns that into a grep.
 */
function checkTestFilenames(): string[] {
  const issues: string[] = [];
  if (!existsSync(testsRoot)) return issues;

  const expected = new Set<string>();
  for (const scope of readdirSync(rulesRoot, { withFileTypes: true })) {
    if (!scope.isDirectory()) continue;
    for (const file of readdirSync(join(rulesRoot, scope.name))) {
      if (!file.endsWith(".yml")) continue;
      expected.add(`${scope.name}-${file.replace(/\.yml$/, "")}-test.yml`);
    }
  }

  for (const file of readdirSync(testsRoot)) {
    if (!file.endsWith(".yml")) continue;
    if (RULE_ID.exec(readFileSync(join(testsRoot, file), "utf-8")) === null) {
      issues.push(`ast-grep/tests/${file}: no \`id:\` — it tests nothing`);
    }
    if (!expected.has(file)) {
      issues.push(
        `ast-grep/tests/${file}: no rule at ast-grep/rules/<scope>/<name>.yml matches this name — ` +
          "a test file is named <scope>-<name>-test.yml after the rule it proves",
      );
    }
  }
  return issues;
}

/** `ast-grep test`: every invalid case must match, every valid case must not. */
function runRuleTests(): string[] {
  const astGrep = AST_GREP_CANDIDATES.find((candidate: string) => {
    if (candidate !== "ast-grep" && !existsSync(candidate)) return false;
    try {
      execFileSync(candidate, ["--version"], { stdio: "pipe", timeout: 5_000 });
      return true;
    } catch {
      return false;
    }
  });
  if (astGrep === undefined) {
    return [
      "ast-grep not found — no structural rule ran or was proven " +
        "(cd frontend && npm install)",
    ];
  }
  try {
    execFileSync(astGrep, ["test", "--config", sgConfig, "--skip-snapshot-tests"], {
      cwd: ompDir,
      encoding: "utf-8",
      timeout: TEST_TIMEOUT_MS,
      stdio: "pipe",
    });
    return [];
  } catch (error: unknown) {
    const output = readOutput(error);
    const failures = output
      .split("\n")
      .filter((line: string) => line.includes("FAIL") || line.startsWith("[Missing]") || line.startsWith("[Noisy]"))
      .map((line: string) => line.trim());
    if (failures.length === 0) {
      return [`ast-grep test failed to run: ${output.split("\n")[0]}`];
    }
    return failures.map((failure: string) => `ast-grep test: ${failure}`);
  }
}

// ============================================================
// Helpers
// ============================================================

function readOutput(error: unknown): string {
  if (error === null || typeof error !== "object") return String(error);
  const stdout = "stdout" in error ? String(error.stdout ?? "") : "";
  const stderr = "stderr" in error ? String(error.stderr ?? "") : "";
  return `${stdout}\n${stderr}`.trim();
}

// Direct execution (make check-ast-rules): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-ast-rules.ts")) {
  const issues = checkAstRulesSync();
  console.log("==> check-ast-rules");
  if (issues.length === 0) {
    console.log("    PASS: every ast-grep rule is proven by a valid/invalid case");
  } else {
    for (const issue of issues) {
      console.log(`    FAIL: ${issue}`);
    }
    printRuleHint("check-ast-rules");
    console.log(`    ${issues.length} issue(s) found`);
    process.exit(1);
  }
}
