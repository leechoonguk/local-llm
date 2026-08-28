import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesStrict } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Makefiles Post Hook
 *
 * After tool execution, verifies that Makefile targets are consistent:
 *   - All .PHONY targets are implemented
 *   - All ## documented targets are in .PHONY
 *   - Documented targets exist in actual Makefile
 *   - Actual Makefile targets are documented
 *   - Every post hook in .omp/hooks/post/ has a corresponding
 *     check-<name> target registered in the root Makefile
 *   - `make verify` runs every post-hook target: a `check-*` target whose
 *     recipe is `node .omp/hooks/post/...` must be a prerequisite of `verify`,
 *     and the prerequisite list must equal the membership documented in
 *     root-makefile.md (both directions). Three targets once existed, passed,
 *     and were never run by the gate — a check that is not in `verify` is a
 *     claim nobody tests.
 *
 * This is a read-only check — it does NOT block tool calls.
 * To fix inconsistencies: update .PHONY, ## documentation, or target implementations.
 */
const cwd = process.cwd();
const ompDir = join(cwd, ".omp");
const rulesDir = join(ompDir, "rules");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


const makefileRules: Array<{ ruleFile: string; makefilePath: string; label: string }> = [
  { ruleFile: "backend-makefile.md", makefilePath: "backend/Makefile", label: "backend" },
  { ruleFile: "frontend-makefile.md", makefilePath: "frontend/Makefile", label: "frontend" },
  { ruleFile: "root-makefile.md", makefilePath: "Makefile", label: "root" },
];

export default function checkMakefiles(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-makefiles", event, () => {
    // Skip read-only tools — they cannot change Makefiles.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesStrict(event, ["Makefile", "makefile"])) return;

    const issues = checkMakefileConsistency();
    if (issues.length === 0) {
      resetSuppression("check-makefiles"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-makefiles",
      issues,
      "update .PHONY, documented targets, or Makefile implementations",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-makefiles") };
  }));
}

function checkMakefileConsistency(): string[] {
  const issues: string[] = [];

  for (const { ruleFile, makefilePath, label } of makefileRules) {
    const rulePath = join(rulesDir, ruleFile);
    if (!existsSync(rulePath)) {
      issues.push(`${label}: rule file ${ruleFile} not found in .omp/rules/`);
      continue;
    }

    const ruleContent = readFileSync(rulePath, "utf-8");
    const ruleTargets = parseMarkdownTable(ruleContent);

    const makefilePathFull = join(cwd, makefilePath);
    if (!existsSync(makefilePathFull)) {
      issues.push(`${label}: Makefile ${makefilePath} not found`);
      continue;
    }

    const actualTargets = parseMakefileTargets(makefilePathFull);
    // A pattern rule with an empty recipe answers *every* unknown target with
    // success, so `make check-anything` passes and the whole gate reads green.
    // Measured: an unattended local model, told its acceptance was
    // `make definitely-not-a-target`, added exactly this to make the predicate
    // pass. A gate that can be satisfied by editing the gate is not a gate.
    for (const hit of catchAllRules(readFileSync(makefilePathFull, "utf-8"))) {
      issues.push(
        `${label}: ${makefilePath} declares a catch-all rule '${hit}' — it answers every unknown ` +
          "target with success, so every check-* gate would pass without running",
      );
    }

    // Check: documented targets not in actual Makefile
    for (const target of ruleTargets) {
      if (!actualTargets.has(target)) {
        issues.push(`${label}: target '${target}' documented in ${ruleFile} but not in actual Makefile`);
      }
    }

    // Check: actual targets not documented
    for (const target of actualTargets) {
      if (!ruleTargets.has(target)) {
        issues.push(`${label}: target '${target}' in Makefile but not documented in ${ruleFile}`);
      }
    }
    // Check: check-* targets must have an executable recipe, not just a
    // documented target header. A blank recipe silently makes verification
    // skip the intended hook.
    issues.push(...checkTargetRecipes(makefilePathFull, label));
    issues.push(...checkTargetHelp(makefilePathFull, label));
  }

  // The decks Makefile has no rule doc of its own, but `make help` is still the
  // only index of how a deck is built.
  issues.push(...checkTargetHelp(join(cwd, "decks", "Makefile"), "decks"));

  // Check: Makefile targets that reference .ts/.sh files must point to
  // existing files. A missing file means the target silently fails.
  for (const { makefilePath, label } of makefileRules) {
    const makefilePathFull = join(cwd, makefilePath);
    if (!existsSync(makefilePathFull)) continue;
    const content = readFileSync(makefilePathFull, "utf-8");
    const lines = content.split(/\r?\n/);
    for (const line of lines) {
      // Match recipe lines: node <path> or bash <path> or ./<path>
      const fileMatch = line.match(/(?:node|bash|\.\/)\s+(\S+\.(?:ts|sh|mjs))\b/);
      if (!fileMatch) continue;
      const refPath = fileMatch[1];
      const fullPath = refPath.startsWith("./") ? join(cwd, refPath) : join(cwd, refPath);
      if (!existsSync(fullPath)) {
        issues.push(`${label}: target references missing file '${refPath}'`);
      }
    }
  }

  // Check: every post hook has a matching check-<name> target in root Makefile
  issues.push(...checkHooksRegisteredInMakefile());

  // Check: every post-hook target is actually run by `make verify`, and the
  // Makefile's prerequisite list matches what root-makefile.md documents.
  issues.push(...checkVerifyMembership());

  return issues;
}

/**
 * A `check-*` target that exists but is not a prerequisite of `verify` passes
 * on its own and is never run by the gate — the harness reports green while one
 * standard goes unproven. Two sources must agree:
 *
 *   1. Makefile: every `check-<name>` whose recipe runs
 *      `node .omp/hooks/post/check-<name>.ts` is in `verify`'s prerequisites.
 *      Targets backed by `lib/` (e.g. `check-api-flow`) need a running stack and
 *      stay out of the hermetic gate by design.
 *   2. root-makefile.md: the `make verify` row lists exactly the prerequisites
 *      the Makefile declares — the doc is the reviewable contract, the Makefile
 *      is the executed one; they drift the moment only one is edited.
 */
function checkVerifyMembership(): string[] {
  const issues: string[] = [];
  const rootMakefilePath = join(cwd, "Makefile");
  const rulePath = join(rulesDir, "root-makefile.md");
  if (!existsSync(rootMakefilePath) || !existsSync(rulePath)) return issues;

  const makefile = readFileSync(rootMakefilePath, "utf-8");
  const actual = parseVerifyPrerequisites(makefile);
  if (actual === null) {
    issues.push("./Makefile: no `verify:` target — the hermetic gate is missing");
    return issues;
  }

  // 1. Every post-hook-backed check-* target must be gated.
  for (const target of parsePostHookTargets(makefile)) {
    if (!actual.has(target)) {
      issues.push(
        `root: target '${target}' runs a post hook but is not a prerequisite of 'verify' — ` +
          "a check outside the gate is never run; add it to verify (and to the root-makefile.md row)",
      );
    }
  }

  // 2. Makefile prerequisites ↔ documented membership, both directions.
  const documented = parseDocumentedVerifyMembers(readFileSync(rulePath, "utf-8"));
  if (documented === null) {
    issues.push("root: root-makefile.md has no `make verify` row listing its members");
    return issues;
  }
  for (const target of actual) {
    if (!documented.has(target)) {
      issues.push(`root: 'verify' runs '${target}' but root-makefile.md's \`make verify\` row does not list it`);
    }
  }
  for (const target of documented) {
    if (!actual.has(target)) {
      issues.push(`root: root-makefile.md documents '${target}' under \`make verify\` but the Makefile does not run it`);
    }
  }
  return issues;
}

/** Prerequisites of `verify:` — backslash continuations joined, `##` help stripped. */
function parseVerifyPrerequisites(makefile: string): Set<string> | null {
  const logical = makefile.replace(/\\\r?\n/g, " ");
  const match = /^verify:[ \t]*([^\n]*)$/m.exec(logical);
  if (match === null) return null;
  const deps = match[1].split("##")[0].trim();
  return new Set(deps.split(/\s+/).filter((token: string) => token.length > 0));
}

/** `check-*` targets whose recipe runs a `.omp/hooks/post/` hook. */
function parsePostHookTargets(makefile: string): Set<string> {
  const targets = new Set<string>();
  let current = "";
  for (const line of makefile.split(/\r?\n/)) {
    const header = /^(check-[A-Za-z0-9_-]+):/.exec(line);
    if (header !== null) {
      current = header[1];
      continue;
    }
    if (current !== "" && /^\t.*node\s+\.omp\/hooks\/post\//.test(line)) {
      targets.add(current);
    }
  }
  return targets;
}

/** Members listed in root-makefile.md's `make verify` row, split on `+`. */
function parseDocumentedVerifyMembers(rule: string): Set<string> | null {
  const row = rule
    .split(/\r?\n/)
    .find((line: string) => /^\|\s*`make verify`\s*\|/.test(line.trim()));
  if (row === undefined) return null;
  const cells = row.split("|").map((cell: string) => cell.trim());
  const command = cells[2] ?? "";
  const members = command
    .replace(/`/g, "")
    .split("+")
    .map((token: string) => token.trim())
    .filter((token: string) => token.length > 0);
  return new Set(members);
}

/**
 * `make help` greps `##` descriptions, so a target without one is invisible: it
 * exists, it is the documented way to do something, and no reader can find it.
 */
function checkTargetHelp(makefilePath: string, label: string): string[] {
  const issues: string[] = [];
  if (!existsSync(makefilePath)) return issues;
  for (const line of readFileSync(makefilePath, "utf-8").split(/\r?\n/)) {
    const match = /^([A-Za-z0-9_-]+):(?!=)/.exec(line);
    if (match === null || match[1] === ".PHONY") continue;
    if (!line.includes("##")) {
      issues.push(`${label}: target '${match[1]}' has no '## <description>' — it cannot appear in \`make help\``);
    }
  }
  return issues;
}

function checkHooksRegisteredInMakefile(): string[] {
  const issues: string[] = [];
  const postHooksDir = join(ompDir, "hooks", "post");
  const rootMakefilePath = join(cwd, "Makefile");

  if (!existsSync(postHooksDir)) {
    issues.push(".omp/hooks/post/ directory not found");
    return issues;
  }
  if (!existsSync(rootMakefilePath)) {
    issues.push("./Makefile: root Makefile not found");
    return issues;
  }

  const rootTargets = parseMakefileTargets(rootMakefilePath);

  for (const hookFile of readdirSync(postHooksDir)) {
    if (!hookFile.endsWith(".ts")) continue;

    // check-<name>.ts → make target <name>
    const targetName = hookFile.replace(/\.ts$/, "");
    if (!rootTargets.has(targetName)) {
      issues.push(`hook: '${hookFile}' not registered as make target '${targetName}' in root Makefile`);
    }
  }

  return issues;
}

function parseMarkdownTable(content: string): Set<string> {
  const targets = new Set<string>();
  const lines = content.split(/\r?\n/);
  let inMakefileTargets = false;

  for (const line of lines) {
    const trimmed = line.trim();

    // Detect section headers — only parse the "Makefile Targets" section
    if (trimmed.startsWith("## ")) {
      inMakefileTargets = trimmed === "## Makefile Targets";
      continue;
    }

    // Only parse in the Makefile Targets section
    if (!inMakefileTargets) continue;

    // Match table rows: | `make target` | ... |
    const rowMatch = trimmed.match(/^\|.*?`make\s+(\S+?)`.*?\|/);
    if (rowMatch) {
      targets.add(rowMatch[1]);
      continue;
    }
  }

  return targets;
}

/**
 * Rules whose target is a bare pattern: `%:`, `%.o:`, `.DEFAULT:`. Each one
 * answers targets nobody wrote, which is indistinguishable from a check that
 * ran and passed.
 */
function catchAllRules(content: string): string[] {
  const found: string[] = [];
  for (const line of content.split(/\r?\n/)) {
    const match = /^(%[^\s:=]*|\.DEFAULT)\s*:(?!=)/.exec(line);
    if (match !== null) found.push(match[1]);
  }
  return found;
}

function parseMakefileTargets(makefilePath: string): Set<string> {
  const content = readFileSync(makefilePath, "utf-8");
  const lines = content.split(/\r?\n/);
  const targets = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();

    // Skip .PHONY, comments, variable assignments
    if (trimmed.startsWith(".PHONY") || trimmed.startsWith("#") || trimmed.includes(":=")) {
      continue;
    }

    const targetMatch = trimmed.match(/^(\S+):\s*(.*)$/);
    if (targetMatch) {
      const targetName = targetMatch[1];
      // Skip special targets and variables
      if (!targetName.startsWith(".") && !targetName.includes("=")) {
        targets.add(targetName);
      }
      continue;
    }
  }

  return targets;
}

function checkTargetRecipes(makefilePath: string, label: string): string[] {
  const issues: string[] = [];
  const lines = readFileSync(makefilePath, "utf-8").split(/\r?\n/);
  let currentTarget = "";
  let hasRecipe = false;

  const flush = (): void => {
    if (currentTarget.startsWith("check-") && !hasRecipe) {
      issues.push(`${label}: target '${currentTarget}' has no recipe`);
    }
  };

  for (const line of lines) {
    const targetMatch = line.trim().match(/^(\S+):\s*(.*)$/);
    if (targetMatch && !targetMatch[1].startsWith(".")) {
      flush();
      currentTarget = targetMatch[1];
      hasRecipe = false;
      continue;
    }

    // Make recipes are tab-indented; ignore blank lines and comments.
    if (currentTarget && /^\s+\S/.test(line) && !line.trimStart().startsWith("#")) {
      hasRecipe = true;
    }
  }
  flush();
  return issues;
}

// Direct execution (make check-makefiles): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-makefiles.ts")) {
  const issues = checkMakefileConsistency();
  console.log("==> check-makefiles");
  if (issues.length === 0) {
    console.log("    PASS: backend / frontend / root Makefiles consistent with rule docs");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-makefiles");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
