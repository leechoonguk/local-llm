import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesStrict } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { execFileSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint, ruleForHook } from "../lib/hook-rule-hint.ts";

declare const process: {
  argv: string[];
  cwd(): string;
  execPath: string;
  exit(code?: number): never;
};

/**
 * Check-Omp-Hooks Post Hook
 *
 * After tool execution, verifies:
 *   1. Directory structure listed in .omp/rules/omp-hooks.md matches
 *      the actual files in .omp/hooks/ (dangling refs / orphans).
 *   2. Functional contract of every hook:
 *      - Post hooks (check-*.ts): the tool_result handler must `return { content }`
 *        that **appends** the warning to the original tool result (spreading
 *        `event.content`). Replacing the content hides the tool output and
 *        causes the agent to repeat the same action (infinite loop).
 *        Per omp://hooks.md, tool_result handlers can return `{ content }`.
 *      - Post hooks must also guard context: skip read-only tools via
 *        `MUTATING_TOOLS` and dedupe repeated warnings via `lastWarning` or `buildSafeWarning`.
 *      - Pre hooks (strict-*.ts): the tool_call handler must `return { block }`
 *        to actually deny tool execution (fail-safe blocking).
 *   3. Rule ↔ Hook 1:1 mapping: every rule in .omp/rules/ maps to ≥1 hook and
 *      every hook maps back to ≥1 rule, per the mapping table in omp-hooks.md.
 *   4. AST rule contract: every ast-grep rule in .omp/ast-grep/rules/ is referenced
 *      by exactly one post hook (via runAstRules), and every post hook that
 *      imports ../lib/ast-rules.ts references at least one rule directory.
 *
 * This is a read-only check — it does NOT block tool calls.
 * To add/remove hooks: update .omp/hooks/* and .omp/rules/omp-hooks.md,
 * then run `make check-omp-hooks` (part of `make verify`) to validate.
 */
const cwd = process.cwd();
const ompDir = join(cwd, ".omp");
const ompHooksMdPath = join(ompDir, "rules", "omp-hooks.md");

/** size+mtime per hook file — an unchanged hook is not re-spawned this session. */
const syntaxCache = new Map<string, string>();

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

export default function checkOmpHooks(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-omp-hooks", event, () => {
    // Skip read-only tools — they cannot change .omp/ files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesStrict(event, [".omp/"])) return;

    const issues = checkOmpHooksSync();
    if (issues.length === 0) {
      resetSuppression("check-omp-hooks");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-omp-hooks",
      issues,
      "update .omp/hooks/* and .omp/rules/omp-hooks.md to be in sync",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-omp-hooks") };
  }));
}

/** Comments and doc prose name forbidden shapes on purpose; only code counts. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((line: string) => line.replace(/^\s*(\/\/|\*).*$/, ""))
    .join("\n");
}

/**
 * A post hook runs *after* a tool has already changed the workspace, so denying
 * the call cannot undo anything — it only strands the agent with an edit it
 * cannot see. Refusal is a pre hook's job; the two are already separated by
 * directory, and this keeps the separation true in the code.
 */
function checkPostHooksNeverBlock(): string[] {
  const issues: string[] = [];
  const postDir = join(ompDir, "hooks", "post");
  if (!existsSync(postDir)) return issues;
  for (const file of readdirSync(postDir)) {
    if (!file.endsWith(".ts")) continue;
    // Comments are stripped first: this file documents the pre-hook shape it is
    // forbidding, and a checker that fails on its own prose is noise.
    const source = stripComments(readFileSync(join(postDir, file), "utf-8"));
    if (/return\s*\{[^}]*block:\s*true/.test(source) || /return\s*\{[^}]*deny:/.test(source)) {
      issues.push(
        `post/${file}: returns a blocking result — a post hook runs after the edit ` +
          "landed, so refusal belongs in a pre hook",
      );
    }
  }
  return issues;
}

function checkOmpHooksSync(): string[] {
  const issues: string[] = [];

  // --- 1. Directory structure sync ---

  // Check omp-hooks.md exists
  if (!existsSync(ompHooksMdPath)) {
    // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
    issues.push(".omp/rules/omp-hooks.md not found");
    return issues;
  }

  // Read omp-hooks.md content
  const content = readFileSync(ompHooksMdPath, "utf-8");

  // List actual hook files in .omp/hooks/
  const hooksDir = join(ompDir, "hooks");
  const listedInMd = new Set<string>();
  const actualFiles = new Set<string>();

  if (!existsSync(hooksDir)) {
    issues.push(".omp/hooks/ directory not found");
    return issues;
  }

  // Read pre/ directory
  const preDir = join(hooksDir, "pre");
  if (existsSync(preDir)) {
    for (const f of readdirSync(preDir)) {
      if (f.endsWith(".ts")) {
        actualFiles.add(`pre/${f}`);
      }
    }
  }

  // Read post/ directory
  const postDir = join(hooksDir, "post");
  if (existsSync(postDir)) {
    for (const f of readdirSync(postDir)) {
      if (f.endsWith(".ts")) {
        actualFiles.add(`post/${f}`);
      }
    }
  }

  // --- lib module naming (omp-hooks.md "lib module naming") ---
  // lib modules are scope-prefixed (backend-*/frontend-*) except the shared
  // runner (ast-rules.ts). A bare domain-*/orm-sync name would collide when
  // frontend checks are added.
  const libDir = join(hooksDir, "lib");
  if (existsSync(libDir)) {
    for (const f of readdirSync(libDir)) {
      if (!f.endsWith(".ts")) continue;
      // An ambient `.d.ts` declares the runtime surface; it exports nothing and
      // is imported by nobody, so a domain scope would be meaningless.
      if (f.endsWith(".d.ts")) continue;
      if (f === "ast-rules.ts") continue; // shared runner — no scope prefix
      // `hook-*` is the shared cross-cutting guard prefix (hook-safety-guard,
      // hook-dormancy): these serve every hook, so no domain scope applies.
      if (/^hook-/.test(f)) continue;
      if (!/^(backend|frontend)-/.test(f)) {
        issues.push(
          `lib/${f}: lib module must be scope-prefixed (backend-*/frontend-*) — ` +
            "see omp-hooks.md 'lib module naming'",
        );
      }
    }
  }

  // --- rule attribution (omp-hooks.md "Rule Attribution") ---
  // Every check's CLI tail must name the rule it enforces via
  // printRuleHint("check-<self>") so a failing `make verify` tells the agent
  // which rule to read, and the check-name -> rule mapping must resolve unless
  // the check is explicitly rule-less. Measured: requirements delivered only
  // as verify failures cost a rediscovery cycle each; the hint closes it.
  const NO_RULE_CHECKS = new Set(["check-omp-types", "check-verify"]);
  for (const f of readdirSync(join(hooksDir, "post"))) {
    if (!f.startsWith("check-") || !f.endsWith(".ts")) continue;
    const name = f.slice(0, -3);
    const src = readFileSync(join(hooksDir, "post", f), "utf-8");
    if (!src.includes("process.argv[1]?.endsWith(")) continue; // no CLI tail
    if (!src.includes(`printRuleHint("${name}")`)) {
      issues.push(
        `post/${f}: CLI tail must call printRuleHint("${name}") before reporting failures — ` +
          "see omp-hooks.md 'Rule Attribution'",
      );
    }
    if (!ruleForHook(name) && !NO_RULE_CHECKS.has(name)) {
      issues.push(
        `post/${f}: no rule resolves for ${name} — add the rule, extend the name map in ` +
          "lib/hook-rule-hint.ts, or list it in NO_RULE_CHECKS with a reason",
      );
    }
  }

  // Extract file list from omp-hooks.md directory structure section
  const lines = content.split("\n");
  let currentDir = ""; // track which directory we're in

  for (const line of lines) {
    // Detect directory: "+-- pre/" or "+-- post/"
    const dirMatch = line.match(/^\+--\s+(\w+)\//);
    if (dirMatch) {
      currentDir = dirMatch[1] + "/";
      continue;
    }

    // Match file lines: "| +-- filename.ts" or "+-- filename.ts"
    const fileMatch = line.match(/^\|?\s*\+--\s+(\S+\.ts)/);
    if (fileMatch && currentDir) {
      const fileName = fileMatch[1];
      listedInMd.add(currentDir + fileName);
    }
  }

  // Check 1: dangling references (listed in md but not on disk)
  for (const listed of listedInMd) {
    if (!actualFiles.has(listed)) {
      issues.push(`${listed}: listed in omp-hooks.md but not found on disk`);
    }
  }

  // Check 2: orphan files (on disk but not listed in md)
  for (const actual of actualFiles) {
    if (!listedInMd.has(actual)) {
      issues.push(`${actual}: found on disk but not listed in omp-hooks.md`);
    }
  }

  // Check 2b: contract-table coverage. The mapping table proves a hook exists;
  // the contract table is what states WHAT it enforces. Five hooks had drifted
  // out of it, so their documented contract was whatever a reader assumed.
  const contractRows = new Set(
    [...content.matchAll(/^\|`(check-[\w-]+\.ts)`\|/gm)].map((m: string[]) => m[1]),
  );
  for (const actual of actualFiles) {
    const [dir, fileName] = actual.split("/");
    if (dir !== "post" || !fileName.startsWith("check-")) continue;
    if (!contractRows.has(fileName)) {
      issues.push(
        `${actual}: missing from the omp-hooks.md contract table — ` +
          "a hook whose checks are undocumented cannot be reviewed or trusted",
      );
    }
  }

  // --- 2. Functional contract of every hook ---

  for (const actual of actualFiles) {
    const [dir, fileName] = actual.split("/");
    const hookPath = join(ompDir, "hooks", dir, fileName);
    const hookContent = readFileSync(hookPath, "utf-8");

    // The whole functional contract below is keyed by the name prefix, so an
    // off-name file (post/foo.ts) would be checked by nothing at all: no
    // guarded() wrapper, no MUTATING_TOOLS filter, no safe warning. The naming
    // convention is therefore a contract, not a preference.
    if (dir === "post" && !fileName.startsWith("check-")) {
      issues.push(
        `${actual}: a post hook must be named check-<scope>-<name>.ts — ` +
          "every post-hook contract check is keyed by that prefix",
      );
    }
    if (dir === "pre" && !fileName.startsWith("strict-")) {
      issues.push(
        `${actual}: a pre hook must be named strict-<scope>-<name>.ts — ` +
          "its blocking contract is keyed by that prefix",
      );
    }

    if (dir === "post" && fileName.startsWith("check-")) {
      // Post hook: must return { content } that APPENDS to the original tool
      // result (spread event.content) — replacing it hides the tool output and
      // causes the agent to repeat the same action (infinite loop).
      if (!/return\s*\{[\s\S]*content\s*:/.test(hookContent)) {
        issues.push(
          `${actual}: tool_result handler does not return { content } — ` +
            "the agent cannot see the warning (console.error only reaches the process log)",
        );
      }
      if (!/buildSafeWarning\(/.test(hookContent)) {
        issues.push(
          `${actual}: must call buildSafeWarning() — direct warning construction bypasses suppression`,
        );
      }
      issues.push(...checkWarningCallShape(actual, fileName, hookContent));
      issues.push(...checkCrashGuard(actual, fileName, hookContent));
      issues.push(...checkDemandDirection(actual, hookContent));
      issues.push(...checkScopeGate(actual, fileName, hookContent));
      if (
        actual !== "post/check-omp-hooks.ts" &&
        /\blet lastWarning\b|warning === lastWarning|lastWarning = warning/.test(hookContent)
      ) {
        issues.push(
          `${actual}: direct lastWarning dedup forbidden — use the shared hook-safety-guard`,
        );
      }
      // Dormancy honesty: a hook that only asserts when a feature exists must
      // say so, or "PASS" means either "compliant" or "nothing to check" and a
      // reader cannot tell which (7 of 34 hooks were in that state).
      if (/Optional feature/i.test(hookContent) && !/hook-dormancy/.test(hookContent)) {
        issues.push(
          `${actual}: declares itself an optional-feature check but never calls dormant() — ` +
            "a dormant check must not print the same PASS as a compliant one",
        );
      }
      // Context economy: must skip read-only tools.
      if (!/MUTATING_TOOLS\.has\(event\.toolName\)/.test(hookContent)) {
        issues.push(
          `${actual}: missing read-only tool filter (MUTATING_TOOLS) — ` +
            "the check runs after every tool call and wastes context",
        );
      }
      if (!/pi\.on\(\s*["']tool_result/.test(hookContent)) {
        issues.push(`${actual}: missing tool_result event handler`);
      }
      // Syntax validity: a hook with a syntax error silently fails to run,
      // masking all its checks. node --check on .ts files strips type
      // annotations (including the `let resetSuppression(...)` pattern),
      // so we use require() which catches TS syntax errors before module
      // resolution. A "Cannot find module" error means syntax is fine.
      issues.push(...checkSyntax(actual, hookPath));
    }

    if (dir === "pre" && fileName.startsWith("strict-")) {
      // Pre hook: must return { block: true } to actually deny tool execution.
      if (!/return\s*\{[\s\S]*block\s*:\s*true/.test(hookContent)) {
        issues.push(
          `${actual}: tool_call handler never returns { block: true } — ` +
            "the hook cannot deny tool execution",
        );
      }
      if (!/pi\.on\("tool_call"/.test(hookContent)) {
        issues.push(`${actual}: missing tool_call event handler`);
      }
      issues.push(...checkPathTagStrip(actual, hookContent));
      issues.push(...checkChannelCoverage(actual, hookContent));
      issues.push(...checkNoCtxDereference(actual, hookContent));
      issues.push(...checkSyntax(actual, hookPath));
    }
  }

  // --- 3. Rule ↔ Hook 1:1 mapping (per the table in omp-hooks.md) ---

  issues.push(...checkPostHooksNeverBlock());
  issues.push(...checkRuleHookMapping(content, actualFiles));

  // --- 3b. Hook name ↔ path scope consistency (omp-naming-consistency.md) ---
  // A check-backend-*/strict-backend-* hook must reference backend paths;
  // check-frontend-* → frontend, check-omp-* → .omp. Prefix-less hooks are
  // cross-cutting by design and exempt.

  issues.push(...checkHookNameScope(actualFiles));

  // --- 4. AST rule contract ---
  // Every ast-grep rule in .omp/ast-grep/rules/ must be referenced by exactly one
  // post hook (via runAstRules), and every post hook importing the runner
  // must reference at least one rule directory.

  issues.push(...checkAstRuleContract(actualFiles));

  // --- 5. One owner per invariant (omp-ast-rules.md) ---
  issues.push(...checkSingleOwnership(actualFiles));

  // --- 6. Feedback and policy boundaries ---
  issues.push(...checkHarnessGuardrails());

  // --- 6b. Authoring invariants for the harness itself ---
  issues.push(...checkAuthoringInvariants(actualFiles));

  // --- 7. Every warning says where it applies ---
  issues.push(...checkIssuesNameTheirPlace());

  return issues;
}

/**
 * Syntax validity: a hook with a syntax error silently fails to run, masking
 * every check it owns. `node --check` cannot read TypeScript, so the module is
 * required in a child process — 36 spawns, which measured 2.3s on every mutating
 * tool result. The result is cached by size+mtime, so unchanged hooks are not
 * re-spawned within a session.
 */
function checkSyntax(actual: string, hookPath: string): string[] {
  const stat = statSync(hookPath);
  const fingerprint = `${stat.size}:${stat.mtimeMs}`;
  if (syntaxCache.get(hookPath) === fingerprint) return [];

  try {
    execFileSync(process.execPath, ["--experimental-strip-types", "-e", `require("${hookPath}")`], { stdio: "pipe" });
  } catch (error: unknown) {
    const stderr = error !== null && typeof error === "object" && "stderr" in error
      ? String(error.stderr ?? "")
      : "";
    // "Cannot find module" = syntax fine, just module resolution (expected).
    if (stderr.includes("ERR_INVALID_TYPESCRIPT_SYNTAX") || stderr.includes("SyntaxError")) {
      return [`${actual}: syntax error — hook cannot execute (run node --check ${hookPath})`];
    }
  }
  syntaxCache.set(hookPath, fingerprint);
  return [];
}

/**
 * One invariant, one owner. An AST rule and a TS regex asserting the same thing
 * drift apart the moment one is edited, and the weaker one (the regex) is what
 * people keep trusting, because it never needed ast-grep to run.
 *
 * Ownership is declared, not guessed: a rule lists the literals it owns under
 * `owns:`, and no post hook may match them in a regex. Inference was tried and
 * rejected — a hook naming `created_by` to require the audit endpoint to
 * *expose* it is a different claim from a rule requiring a *comparison* with it.
 */
function checkSingleOwnership(actualFiles: Set<string>): string[] {
  const issues: string[] = [];
  const astRulesRoot = join(ompDir, "ast-grep", "rules");
  if (!existsSync(astRulesRoot)) return issues;

  const owned = new Map<string, string>(); // declared token → owning rule file
  for (const dir of readdirSync(astRulesRoot, { withFileTypes: true })) {
    if (!dir.isDirectory()) continue;
    for (const file of readdirSync(join(astRulesRoot, dir.name))) {
      if (!file.endsWith(".yml")) continue;
      const source = readFileSync(join(astRulesRoot, dir.name, file), "utf-8");
      for (const token of declaredOwnedTokens(source)) {
        owned.set(token, `ast-grep/rules/${dir.name}/${file}`);
      }
    }
  }

  for (const actual of actualFiles) {
    if (!actual.startsWith("post/")) continue;
    const hookContent = readFileSync(join(ompDir, "hooks", actual), "utf-8");
    // Only regex literals count: a comment or a message may name the same symbol
    // precisely to point at the rule that owns it — and a doc path such as
    // `.omp/ast-grep/rules/environment/` reads as a regex to any scanner.
    const code = hookContent
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .map((line: string) => line.replace(/^\s*(\/\/|\*).*$/, ""))
      .join("\n");
    const patterns = [...code.matchAll(/\/(?:\\.|\[[^\]]*\]|[^/\n\\])+\/[gimsuy]*/g)].map(
      (match: string[]) => match[0],
    );
    for (const [token, ruleFile] of owned) {
      if (!patterns.some((pattern: string) => pattern.includes(token))) continue;
      issues.push(
        `${actual}: regex matches "${token}", declared owned by ${ruleFile} — one invariant, ` +
          "one owner (omp-ast-rules.md): delete the regex, or drop the token from `owns:`",
      );
    }
  }
  return issues;
}

/** The `owns:` list a rule declares — the tokens no TS regex may re-implement. */
function declaredOwnedTokens(ruleSource: string): string[] {
  const block = /^owns:\n((?:\s+-\s+.*\n)+)/m.exec(ruleSource);
  if (block === null) return [];
  return [...block[1].matchAll(/^\s+-\s+"?(.*?)"?\s*$/gm)].map((match: string[]) => match[1]);
}

/**
 * The safety-guard call shape is a contract, not a style preference.
 * `buildSafeWarning(toolName, hookName, issues, fixHint)` called with three
 * arguments shifts `issues` onto `hookName` and a string onto `issues`, and the
 * hook dies at runtime with "visible.map is not a function" — every check in
 * that hook silently stops running. The hook name must also equal the file's
 * own name, because the guard renders it as `make <hookName>` in the fix hint.
 */
function checkWarningCallShape(actual: string, fileName: string, hookContent: string): string[] {
  const issues: string[] = [];
  const hookName = fileName.replace(/\.ts$/, "");
  const call = /buildSafeWarning\(\s*([^;]*?)\s*\);/.exec(hookContent);
  if (call === null) return issues;

  const args = splitArguments(call[1]);
  if (args.length !== 4) {
    issues.push(
      `${actual}: buildSafeWarning() called with ${args.length} argument(s) — the shape is ` +
        "(event.toolName, hookName, issues, fixHint); a missing toolName makes the hook " +
        'die with "visible.map is not a function"',
    );
    return issues;
  }
  if (args[0] !== "event.toolName") {
    issues.push(`${actual}: buildSafeWarning()'s first argument must be event.toolName`);
  }
  if (args[2] !== "issues") {
    issues.push(`${actual}: buildSafeWarning()'s third argument must be the issues array`);
  }
  const declaredNames = [
    args[1],
    ...[...hookContent.matchAll(/wrapWarning\(warning,\s*event\.content,\s*("[^"]+")/g)].map(
      (match: string[]) => match[1],
    ),
    ...[...hookContent.matchAll(/resetSuppression\(\s*("[^"]+")/g)].map(
      (match: string[]) => match[1],
    ),
  ];
  for (const name of declaredNames) {
    if (name !== `"${hookName}"`) {
      issues.push(
        `${actual}: hook name ${name} does not match the file (expected "${hookName}") — ` +
          `the guard renders it as "make ${hookName}", which must be a real target`,
      );
    }
  }
  return issues;
}

/**
 * Crash visibility is a contract, not a nicety. The extension runner catches a
 * `tool_result` handler's throw, reports it to its own log and continues — the
 * conversation never sees it and the hook's overrides are dropped, so the hook
 * silently stops enforcing everything it owns while its `make` target stays
 * green. Routing the handler body through `guarded()` is what turns that into a
 * visible `<system-notice>` plus a line in `.omp/state/hook-crash.log`.
 */
/**
 * 경로 스코프 계약 — 훅은 자기 도메인 이벤트에만 돈다(omp-hooks.md "Path gate").
 * 실측 2026-08-29: 변이 도구 결과 1회에 post 훅 36개가 write 6.8초/bash 4.9초를 썼고,
 * 그 절반이 이벤트와 무관한 하네스 메타 검사였다. 비용은 컨텍스트가 아니라 벽시계다.
 */
function checkScopeGate(actual: string, _fileName: string, hookContent: string): string[] {
  if (/\btouchesPath\s*\(|\btouchesStrict\s*\(/.test(hookContent)) return [];
  if (/\/\/\s*hook-scope:\s*global\s*—\s*\S/.test(hookContent)) return [];
  return [
    `${actual}: declares no path scope — gate the handler with touchesPath()/touchesStrict() ` +
      "from lib/hook-scope.ts, or state `// hook-scope: global — <reason>` (omp-hooks.md, Path gate)",
  ];
}

/**
 * 요구 방향 계약 — 검사는 **존재하는 하류가 상류를 요구**한다. 작업의 첫 걸음에서 마지막 걸음을
 * 요구하면 안 된다.
 *
 * 근거(2026-08-29 실측): `app/models/x.py` 하나가 생기는 순간 schema/repository/service 누락과
 * 라우터 미등록·DI 미배선까지 5건이 한꺼번에 나갔다. 이 지적들은 매 변이 도구 결과에 주입되고,
 * 로컬 모델은 목록을 작업 큐로 읽는다("첫 실패 수정 완료. 다음: missing service file") — 한 계층만
 * 요청한 프롬프트가 기능 전체로 부풀었다.
 *
 * 기계 판정: 파일/등록의 **부재**를 지적하는 문장은 둘 중 하나여야 한다.
 *  (a) 무엇 때문에 요구가 발생했는지 메시지가 밝힌다 — `… exists but …` 형태(앵커 명시), 또는
 *  (b) 그 줄 위 5줄 안에 `// premature-ok: <사유>` 가 있다(어느 단계에서든 참인 요구).
 * 내용 검사(클래스·메서드·필드 부재)는 대상이 아니다 — 그건 이미 존재하는 파일의 속성이다.
 */
function checkDemandDirection(actual: string, hookContent: string): string[] {
  const EXISTENCE = /(missing \w+ file|file is missing|not included in|not imported in|[\w./-]+\.(?:py|http|md|ts)\)? not found)/i;
  const lines = hookContent.split("\n");
  const issues: string[] = [];
  lines.forEach((line, i) => {
    if (!/issues\.push\(/.test(line) || !EXISTENCE.test(line)) return;
    const near = lines.slice(Math.max(0, i - 5), i + 1).join("\n");
    if (line.includes(" exists") || /premature-ok:\s*\S/.test(near)) return;
    issues.push(`${actual}:${i + 1}: 존재 요구가 앵커를 밝히지 않는다 — \`… exists but …\` 로 무엇 때문에 요구가 생겼는지 적거나, 어느 단계에서든 참이면 \`// premature-ok: <사유>\` 를 단다 (omp-hooks.md, Demand direction)`);
  });
  return issues;
}

function checkCrashGuard(actual: string, fileName: string, hookContent: string): string[] {
  const issues: string[] = [];
  const hookName = fileName.replace(/\.ts$/, "");
  if (!/import \{ guarded \} from "\.\.\/lib\/hook-visibility\.ts";/.test(hookContent)) {
    issues.push(
      `${actual}: does not import guarded() from lib/hook-visibility.ts — ` +
        "an exception in the handler is swallowed by the runner and every check " +
        "this hook owns stops running silently",
    );
    return issues;
  }
  // Counted, not merely found: a file may register a second `tool_result`
  // handler, and checking only the first match would leave that one bare —
  // exactly the invisible-crash hole this contract exists to close.
  const registrations = [...hookContent.matchAll(/pi\.on\(\s*["']tool_result["']/g)].length;
  const delegations = [...hookContent.matchAll(/\)\s*=>\s*guarded\(\s*("[^"]*")\s*,\s*event\s*,/g)];
  if (delegations.length < registrations) {
    issues.push(
      `${actual}: ${registrations} tool_result handler(s) but ${delegations.length} ` +
        `guarded() wrapper(s) — every body must read \`(event) => guarded("${hookName}", ` +
        "event, () => { ... })\`; code outside the wrapper still throws invisibly",
    );
    return issues;
  }
  for (const delegation of delegations) {
    if (delegation[1] === `"${hookName}"`) continue;
    issues.push(
      `${actual}: guarded() names ${delegation[1]} (expected "${hookName}") — ` +
        `the crash notice tells the reader to re-run "make <name>"`,
    );
  }
  return issues;
}

/**
 * 경로 정규화 계약 — 앵커드 편집은 경로에 내용 태그를 붙인다(`main.py#0D77`). 그 문자열을 그대로
 * 허용 목록·확장자·디렉터리 접두와 맞추면 **어디에도 없는 경로**를 판정하는 것이라, 정당한 편집을
 * 막거나(모델은 셸로 우회한다) 정책을 조용히 통과시킨다 — 둘 다 밖에서는 보이지 않는다.
 * 경로를 읽는 자리에서 태그를 벗기거나, 위 5줄 안에 `// path-raw-ok: <사유>` 를 단다.
 * (omp-hooks.md, "Reading the edited path")
 */
function checkPathTagStrip(actual: string, hookContent: string): string[] {
  const issues: string[] = [];
  const lines = hookContent.split("\n");
  const TAG_STRIP = /#\[0-9A-Fa-f\]\{4\}\$/;
  lines.forEach((line, i) => {
    if (/^\s*(\/\/|\*)/.test(line)) return; // 주석은 이 모양을 설명하려고 적기도 한다
    if (!/\binput\b/.test(line) || !/\.path\b/.test(line)) return;
    // 한 문장이 여러 줄에 걸칠 수 있으므로 읽은 줄부터 두 줄까지를 같은 문장으로 본다.
    if (TAG_STRIP.test(lines.slice(i, i + 3).join("\n"))) return;
    if (/path-raw-ok:\s*\S/.test(lines.slice(Math.max(0, i - 5), i + 1).join("\n"))) return;
    issues.push(`${actual}:${i + 1}: 앵커드 편집의 내용 태그를 벗기지 않고 경로를 매칭한다 — 읽는 자리에서 태그를 벗기거나(4자리 16진 접미), 어느 모양으로 와도 옳으면 \`// path-raw-ok: <사유>\` 를 단다 (omp-hooks.md, Reading the edited path)`);
  });
  return issues;
}

/**
 * 채널 계약 — 명령은 `bash` 로만 오지 않는다. `eval` 도구는 파이썬/JS 본문을 `input.code` 로
 * 싣고, 그 본문은 `subprocess.run([...])`·`execSync(...)` 로 같은 바이너리에 닿는다. 명령 문자열을
 * 검사하면서 `bash` 만 거르는 가드는 다음 도구 호출이 그대로 걸어 나가는 정책을 선언하는 것이다.
 * 셸 전용 정책이 정말 맞다면 `// channel-ok: <사유>` 로 밝힌다.
 * (omp-hooks.md, "Every execution channel")
 */
function checkChannelCoverage(actual: string, hookContent: string): string[] {
  const code = stripComments(hookContent);
  if (!/\binput\b[^\n]*\.command\b/.test(code)) return [];
  if (/["']eval["']/.test(code) && /\binput\b[^\n]*\.code\b/.test(code)) return [];
  if (/channel-ok:\s*\S/.test(hookContent)) return [];
  return [
    `${actual}: 명령 문자열을 검사하면서 \`eval\` 채널을 받지 않는다 — 도구 필터에 \`eval\` 을 넣고 \`input.code\` 를 \`input.command\` 와 같이 읽거나, 셸 전용이 맞으면 \`// channel-ok: <사유>\` 를 단다 (omp-hooks.md, Every execution channel)`,
  ];
}

/**
 * 컨텍스트 비참조 계약 — `tool_call` 핸들러의 두 번째 인자는 확장 컨텍스트다. pre 훅의 예외는
 * **도구 실패로 승격**돼 도구 호출 자체가 죽고, 에이전트는 결과 대신 크래시를 받는다. 컨텍스트를
 * 읽는 모든 줄이 그 후보다(호출 모양에 따라 없는 속성, 던지는 getter). 차단 판단은 `event` 만으로
 * 하고 인자는 `_ctx: unknown` 으로 받는다. 정말 필요하면 `// ctx-ok: <사유>` 로 밝힌다.
 * (omp-hooks.md, "The context parameter is not readable")
 */
function checkNoCtxDereference(actual: string, hookContent: string): string[] {
  const issues: string[] = [];
  const code = stripComments(hookContent);
  if (/ctx-ok:\s*\S/.test(hookContent)) return issues;
  for (const handler of code.matchAll(/pi\.on\(\s*["']tool_call["']\s*,\s*(?:async\s*)?\(([^)]*)\)/g)) {
    const parameters = splitArguments(handler[1]);
    const contextName = (parameters[1] ?? "").split(":")[0].trim();
    if (contextName === "") continue;
    // 선언 자체를 지운 나머지에서 이름이 한 번이라도 보이면 쓰고 있는 것이다. `(ctx as any).x`
    // 처럼 캐스팅을 거치거나 헬퍼로 넘겨도 결국 같은 읽기라서, 모양이 아니라 등장으로 센다.
    if (!new RegExp(`\\b${contextName}\\b`).test(code.replace(handler[0], ""))) continue;
    issues.push(`${actual}: tool_call 핸들러가 컨텍스트 인자 \`${contextName}\` 를 읽는다 — 거기서 던지면 도구 호출이 죽는다(예외는 도구 실패로 승격). \`event\` 만으로 판단하거나 \`// ctx-ok: <사유>\` 를 단다 (omp-hooks.md, The context parameter is not readable)`);
  }
  return issues;
}

/**
 * Splits an argument list at top-level commas only: a fix hint such as
 * "update .PHONY, documented targets, or ..." would otherwise read as three
 * extra arguments and report a shape violation that does not exist.
 */
function splitArguments(source: string): string[] {
  const args: string[] = [];
  let current = "";
  let depth = 0;
  let quote = "";
  for (const character of source) {
    if (quote !== "") {
      current += character;
      if (character === quote) quote = "";
      continue;
    }
    if (character === '"' || character === "'" || character === "`") {
      quote = character;
      current += character;
      continue;
    }
    if ("([{".includes(character)) depth += 1;
    if (")]}".includes(character)) depth -= 1;
    if (character === "," && depth === 0) {
      args.push(current.trim());
      current = "";
      continue;
    }
    current += character;
  }
  if (current.trim() !== "") args.push(current.trim());
  return args;
}

/**
 * Authoring invariants for the harness itself.
 *
 * Each one exists because the measured shape of this harness says the class can
 * grow: hook cost concentrated in one shell-out (54% of all hook time in 2,297
 * measured runs), twenty-three post hooks that have never warned once, and a
 * loop detector kind (`oscillation`) that is declared, produced and judged by
 * nobody. A guardrail is cheaper than the audit that finds these again.
 */
function checkAuthoringInvariants(actualFiles: Set<string>): string[] {
  const issues: string[] = [];
  const postDir = join(ompDir, "hooks", "post");

  // 1. Every post hook stays off read-only tools. Measured: all 36 already do,
  //    so this only holds the line - a hook that runs after `read` pays its cost
  //    on turns that cannot have broken anything.
  // `actualFiles` carries directory-prefixed names ("post/check-x.ts"), and the
  // first version of this loop filtered on "check-" - matching nothing, so the
  // invariants below never ran. Measured by mutating a hook to spawn `make`.
  for (const entry of [...actualFiles].filter((name) => name.startsWith("post/check-"))) {
    const fileName = entry.slice("post/".length);
    const path = join(postDir, fileName);
    if (!existsSync(path)) continue;
    const source = readFileSync(path, "utf-8");
    if (!/MUTATING_TOOLS/.test(source)) {
      issues.push(
        `post/${fileName}: must gate on MUTATING_TOOLS — a check that runs after a read spends ` +
          "context on a turn that changed nothing",
      );
    }
    // 2. The project gate is expensive and belongs to one owner. `check-verify`
    //    runs `make verify`; a second hook doing the same doubles the cost and
    //    races the agent's own make.
    if (fileName === "check-verify.ts") continue;
    const executes = /(spawnSync|execSync|execFileSync)\(\s*["'](make|pytest|ruff|pyright|npm|uv)["']/.exec(source);
    if (executes !== null) {
      issues.push(
        `post/${fileName}: runs '${executes[2]}' itself — only post/check-verify.ts may execute the ` +
          "project gate, and everything else must read files instead of running builds",
      );
    }
  }

  return issues;
}

function checkHarnessGuardrails(): string[] {
  const issues: string[] = [];
  const safetyGuardPath = join(ompDir, "hooks", "lib", "hook-safety-guard.ts");
  const verifyHookPath = join(ompDir, "hooks", "post", "check-verify.ts");
  const migrationPolicyPath = join(ompDir, "hooks", "lib", "backend-migration-policy.ts");
  const integrationConfigPath = join(ompDir, "hooks", "lib", "backend-integration-configuration.ts");
  const migrationPreHookPath = join(ompDir, "hooks", "pre", "strict-backend-migrations.ts");
  const noSubagentsHookPath = join(ompDir, "hooks", "pre", "strict-no-subagents.ts");
  const visibilityGuardPath = join(ompDir, "hooks", "lib", "hook-visibility.ts");

  if (existsSync(safetyGuardPath)) {
    const safetyGuard = readFileSync(safetyGuardPath, "utf-8");
    if (!/const key = .*hookName.*summary/.test(safetyGuard)) {
      issues.push("lib/hook-safety-guard.ts: warning suppression must be keyed by hook and issue set");
    }
    if (!/\.\.\.\(originalContent\s*\?\?\s*\[\]\)/.test(safetyGuard)) {
      issues.push("lib/hook-safety-guard.ts: warning wrapper must append original tool content");
    }
  }

  if (existsSync(verifyHookPath)) {
    const verifyHook = readFileSync(verifyHookPath, "utf-8");
    if (!/isMakeCommand\(event\.input\)/.test(verifyHook)) {
      issues.push("post/check-verify.ts: explicit make commands must skip nested verification");
    }
  }

  if (existsSync(migrationPolicyPath) && existsSync(migrationPreHookPath)) {
    const migrationPolicy = readFileSync(migrationPolicyPath, "utf-8");
    const migrationPreHook = readFileSync(migrationPreHookPath, "utf-8");
    if (!/export function isPushedMigration\(/.test(migrationPolicy)) {
      issues.push("lib/backend-migration-policy.ts: shared isPushedMigration() is required");
    }
    if (!/isPushedMigration as isUpstreamMigration/.test(migrationPreHook)) {
      issues.push("pre/strict-backend-migrations.ts: must import the shared upstream policy helper");
    }
    if (/spawnSync\(\s*["']git/.test(migrationPreHook)) {
      issues.push("pre/strict-backend-migrations.ts: must not duplicate Git upstream policy");
    }
  }
  if (existsSync(integrationConfigPath)) {
    const integrationConfig = readFileSync(integrationConfigPath, "utf-8");
    if (!/listIntegrationMigrationFiles\(\)/.test(integrationConfig)) {
      issues.push("lib/backend-integration-configuration.ts: must discover integration migrations");
    }
    if (/for \(const revision of \[/.test(integrationConfig)) {
      issues.push("lib/backend-integration-configuration.ts: hardcoded integration revision lists are forbidden");
    }
  }
  if (existsSync(noSubagentsHookPath)) {
    const noSubagentsHook = readFileSync(noSubagentsHookPath, "utf-8");
    if (!/if \(event\.toolName !== ["']task["']\) return;/.test(noSubagentsHook)) {
      issues.push("pre/strict-no-subagents.ts: must block every task tool invocation");
    }
    if (/\.agent\s*===/.test(noSubagentsHook)) {
      issues.push("pre/strict-no-subagents.ts: agent-type allowlists are bypassable and forbidden");
    }
  }
  if (existsSync(visibilityGuardPath)) {
    const visibilityGuard = readFileSync(visibilityGuardPath, "utf-8");
    if (!/appendFileSync\(crashLog/.test(visibilityGuard)) {
      issues.push(
        "lib/hook-visibility.ts: a crash must be appended to the crash log — " +
          "a notice alone dies with the session",
      );
    }
    if (!/content: \[\.\.\.original,/.test(visibilityGuard)) {
      issues.push(
        "lib/hook-visibility.ts: the crash notice must append to the original tool content",
      );
    }
    if (/\bthrow\b/.test(stripComments(visibilityGuard))) {
      issues.push(
        "lib/hook-visibility.ts: must not rethrow — one broken hook cannot decide " +
          "what the others get to report",
      );
    }
  }

  return issues;
}


/**
 * Verifies hook name ↔ path scope consistency per omp-naming-consistency.md:
 * a scoped hook (check-backend-*, strict-backend-*, check-frontend-*,
 * check-omp-*, strict-omp-*) must reference its scope's top-level path in
 * its code. Prefix-less hooks (check-makefiles, check-verify,
 * strict-command-routing, strict-no-subagents) are cross-cutting — exempt.
 */
function checkHookNameScope(actualFiles: Set<string>): string[] {
  const issues: string[] = [];
  const scopeByPrefix: Array<{ prefix: string; path: string }> = [
    { prefix: "backend-", path: "backend" },
    { prefix: "frontend-", path: "frontend" },
    { prefix: "omp-", path: ".omp" },
  ];

  for (const actual of actualFiles) {
    const fileName = actual.split("/").pop() ?? "";
    const hookPath = join(ompDir, "hooks", actual);
    const hookContent = readFileSync(hookPath, "utf-8");

    // Strip the check-/strict- prefix, then match the scope: check-backend-*
    // → backend, check-omp-* → omp, etc.
    const scoped = fileName.replace(/^(check|strict)-/, "");
    for (const { prefix, path } of scopeByPrefix) {
      if (!scoped.startsWith(prefix)) continue;
      // The scope must appear as an actual path reference, not just in the
      // docstring (a hook's own name mentions its scope). Path contexts:
      //   - "backend/" or "backend\/" (string/regex path)
      //   - join(..., "backend", ...) path join argument
      const inPath = hookContent.includes(`${path}/`) || hookContent.includes(`${path}\\/`);
      const inJoin = new RegExp(`join\\([^)]*["']${path}["']`).test(hookContent);
      const inScopedLib = hookContent.includes(`../lib/${prefix}`);
      if (!inPath && !inJoin && !inScopedLib) {
        issues.push(
          `${actual}: ${prefix} hook has no path reference to ${path}/ ` +
            `(join(), path string, or scoped lib import) — name says ${prefix} but the code ` +
            "governs another scope — see omp-naming-consistency.md",
        );
      }
    }
  }

  return issues;
}

/**
 * Verifies the AST rule contract:
 *   - every ast-grep rule YAML under .omp/ast-grep/rules/ is referenced by
 *     exactly one post hook
 *   - every post hook that imports ../lib/ast-rules.ts references ≥1 rule dir
 *   - rule filenames follow <subject>-<property>.yml (no scope prefix, no
 *     abbreviations, lowercase hyphen-separated) per omp-ast-rules.md
 *   - the "AST Rule Contract" table in omp-hooks.md and the AST mapping
 *     tables in the domain rules (backend-domain/batch/environment) list
 *     exactly the rule files on disk (3-way sync: docs ↔ disk ↔ hooks)
 */
function checkAstRuleContract(actualFiles: Set<string>): string[] {
  const issues: string[] = [];
  const astRulesRoot = join(ompDir, "ast-grep", "rules");
  if (!existsSync(astRulesRoot)) return issues;

  // Collect rule files per subdirectory
  const ruleDirs = new Map<string, string[]>(); // dir → rule files
  for (const dir of readdirSync(astRulesRoot)) {
    const dirPath = join(astRulesRoot, dir);
    if (!existsSync(dirPath) || !readdirSync(dirPath).some((f: string) => f.endsWith(".yml"))) continue;
    ruleDirs.set(dir, readdirSync(dirPath).filter((f: string) => f.endsWith(".yml")));
  }

  // --- Naming: <subject>-<property>.yml, no scope prefix/abbreviation ---
  for (const [dir, files] of ruleDirs) {
    for (const file of files) {
      const base = file.replace(/\.yml$/, "");
      if (!/^[a-z]+(-[a-z]+)+$/.test(base)) {
        issues.push(
          `ast-grep/rules/${dir}/${file}: filename must be <subject>-<property>.yml ` +
            "(lowercase, hyphen-separated, at least two words)",
        );
        continue;
      }
      // Scope prefix must not be repeated in the filename (batch/batch-*.yml)
      if (base.startsWith(`${dir}-`)) {
        issues.push(
          `ast-grep/rules/${dir}/${file}: scope prefix "${dir}-" duplicated — ` +
            "the directory is the scope, filename is <subject>-<property> only",
        );
      }
      // No abbreviated scope (env- for environment/)
      if (dir === "environment" && base.startsWith("env-")) {
        issues.push(
          `ast-grep/rules/${dir}/${file}: abbreviated scope "env-" — ` +
            "use the full scope directory name, filename is <subject>-<property> only",
        );
      }
    }
  }

  // --- 3-way sync: docs tables ↔ disk ---
  // omp-hooks.md "AST Rule Contract" table + domain rule mapping tables must
  // list exactly the rule files on disk (no stale names, no orphans).
  issues.push(...checkAstRuleDocSync(ruleDirs));

  // Collect which rule dirs each post hook references
  const hookRefs = new Map<string, Set<string>>(); // hook file → rule dirs
  for (const actual of actualFiles) {
    if (!actual.startsWith("post/") || !actual.endsWith(".ts")) continue;
    const hookPath = join(ompDir, "hooks", actual);
    const hookContent = readFileSync(hookPath, "utf-8");
    if (!/import\s*\{[^}]*runAstRules[^}]*\}\s*from\s*["']\.\.\/lib\/ast-rules/.test(hookContent)) continue;

    const refs = new Set<string>();
    for (const dir of ruleDirs.keys()) {
      if (hookContent.includes(`"rules", "${dir}"`) || hookContent.includes(`'rules', '${dir}'`)) {
        refs.add(dir);
      }
    }
    hookRefs.set(actual, refs);
  }

  // Every rule dir must be referenced by exactly one hook
  for (const [dir, files] of ruleDirs) {
    const refs = [...hookRefs.entries()].filter(([, refs]) => refs.has(dir));
    if (refs.length === 0) {
      issues.push(`ast-grep/rules/${dir}/ (${files.length} rule(s)) not referenced by any post hook`);
    } else if (refs.length > 1) {
      issues.push(`ast-grep/rules/${dir}/ referenced by multiple hooks: ${refs.map(([h]) => h).join(", ")}`);
    }
  }

  // Every hook using the runner must reference ≥1 rule dir
  for (const [hook, refs] of hookRefs) {
    if (refs.size === 0) {
      issues.push(`${hook}: imports runAstRules but references no .omp/ast-grep/rules/ subdirectory`);
    }
  }

  return issues;
}

/**
 * Verifies the 3-way sync between the AST rule docs and the rule files on
 * disk. Two doc sources are checked:
 *   1. omp-hooks.md "AST Rule Contract" table — lists every rule file
 *   2. domain rule mapping tables (backend-domain.md, backend-batch.md,
 *      environment.md "Validation (Post-Hook)" sections) — list the
 *      rule files for their scope
 * Every file listed in a doc must exist on disk (no stale names), and every
 * file on disk must be listed in the matching doc (no orphans).
 */
function checkAstRuleDocSync(ruleDirs: Map<string, string[]>): string[] {
  const issues: string[] = [];
  const rulesDir = join(ompDir, "rules");

  // Collect every rule filename mentioned in the docs, per scope dir.
  // Doc sources: omp-hooks.md AST Rule Contract table + domain rule tables.
  const docFiles = new Map<string, Set<string>>(); // dir → filenames in docs
  const docSources = [
    { file: "omp-hooks.md", section: "AST Rule Contract" },
    { file: "backend-domain.md", section: "Validation (Post-Hook)" },
    { file: "backend-batch.md", section: "Validation (Post-Hook)" },
    { file: "environment.md", section: "Validation (Post-Hook)" },
  ];

  for (const { file, section } of docSources) {
    const path = join(rulesDir, file);
    if (!existsSync(path)) continue;
    const content = readFileSync(path, "utf-8");

    // Find the section, then collect `*.yml` backtick references in it.
    const lines = content.split("\n");
    let inSection = false;
    for (const line of lines) {
      if (line.startsWith("## ")) {
        inSection = line.slice(3).trim() === section;
        continue;
      }
      if (!inSection) continue;
      for (const m of line.matchAll(/`([a-z0-9-]+\.yml)`/g)) {
        const name = m[1];
        // Map the file to its scope dir by matching against disk dirs.
        for (const [dir, files] of ruleDirs) {
          if (files.includes(name)) {
            if (!docFiles.has(dir)) docFiles.set(dir, new Set());
            docFiles.get(dir)!.add(name);
          }
        }
      }
    }
  }

  // Every file on disk must be listed in the docs (no orphans).
  for (const [dir, files] of ruleDirs) {
    const listed = docFiles.get(dir) ?? new Set<string>();
    for (const file of files) {
      if (!listed.has(file)) {
        issues.push(
          `ast-grep/rules/${dir}/${file}: on disk but not listed in any doc ` +
            "(omp-hooks.md AST Rule Contract or the domain rule's Validation table)",
        );
      }
    }
  }

  // Every file listed in the docs must exist on disk (no stale names).
  for (const [dir, listed] of docFiles) {
    const files = ruleDirs.get(dir) ?? [];
    for (const name of listed) {
      if (!files.includes(name)) {
        issues.push(
          `ast-grep/rules/${dir}/${name}: listed in docs but not found on disk — ` +
            "stale reference (rename the file or update the docs)",
        );
      }
    }
  }

  return issues;
}

/**
 * Parses the "Rule ↔ Hook Mapping" table in omp-hooks.md and verifies the
 * 1:1 contract: every rule file maps to ≥1 hook, every hook file maps back
 * to ≥1 rule. Orphans on either side are violations.
 *
 * Also enforces the 1:1 separation principle (omp-hooks.md): a post hook
 * should not be shared by multiple rules of the same scope — when a rule
 * grows beyond one domain, split a new rule + hook pair instead of appending
 * to an existing hook. Exceptions: cross-cutting hooks (check-makefiles,
 * check-verify, check-omp-*) and pre hooks (strict-command-routing).
 */
function checkRuleHookMapping(mdContent: string, actualFiles: Set<string>): string[] {
  const issues: string[] = [];
  const rulesDir = join(ompDir, "rules");

  // Parse the mapping table rows: | `rule.md` | `hook.ts` | `hook.ts` |
  const mappedRules = new Set<string>();
  const mappedHooks = new Set<string>();
  const hookToRules = new Map<string, string[]>(); // hook → rules
  const lines = mdContent.split("\n");
  let inMapping = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("## ")) {
      inMapping = trimmed === "## Rule ↔ Hook Mapping";
      continue;
    }
    if (!inMapping) continue;

    const cells = trimmed.match(/^\|(.*)\|$/);
    if (!cells) continue;
    const cols = cells[1].split("|").map((c) => c.trim());
    if (cols.length < 2) continue;

    const ruleMatch = cols[0].match(/`([^`]+\.md)`/);
    if (!ruleMatch) continue;
    const ruleFile = ruleMatch[1];
    mappedRules.add(ruleFile);

    for (let i = 1; i < cols.length; i++) {
      // Every hook in the cell, not just the first: a rule enforced by two
      // hooks is written `a.ts + b.ts`, and reading one of them left the other
      // reported as unmapped.
      for (const hookMatch of cols[i].matchAll(/`([^`]+\.ts)`/g)) {
        const hook = hookMatch[1];
        mappedHooks.add(hook);
        if (!hookToRules.has(hook)) hookToRules.set(hook, []);
        hookToRules.get(hook)!.push(ruleFile);
      }
    }
  }

  // Every rule file must be mapped to ≥1 hook
  if (existsSync(rulesDir)) {
    for (const f of readdirSync(rulesDir)) {
      if (!f.endsWith(".md")) continue;
      if (!mappedRules.has(f)) {
        issues.push(`rule '${f}' not mapped to any hook in omp-hooks.md mapping table`);
      }
    }
  }

  // Every hook file must be mapped back to ≥1 rule
  for (const actual of actualFiles) {
    const fileName = actual.split("/").pop() ?? "";
    if (!mappedHooks.has(fileName)) {
      issues.push(`hook '${actual}' not mapped to any rule in omp-hooks.md mapping table`);
    }
  }

  // 1:1 separation: a post hook shared by multiple same-scope rules is a
  // sign the hook grew beyond one domain — split it. Cross-cutting hooks
  // (check-makefiles, check-verify, check-omp-*) and pre hooks are exempt.
  // TTSR trigger rules are exempt too: they add no validation domain, they
  // deliver an invariant an existing hook already owns at the moment it is
  // about to be violated, so they *must* map to that hook.
  const ttsrRules = listTtsrRules(rulesDir);
  for (const [hook, rules] of hookToRules) {
    const owned = rules.filter((rule) => !ttsrRules.has(rule));
    if (owned.length <= 1) continue;
    if (hook.startsWith("check-makefiles") || hook.startsWith("check-verify") || hook.startsWith("check-omp-") || hook.startsWith("strict-")) continue;
    const scopes = new Set(owned.map((r) => r.replace(/\.md$/, "").split("-")[0]));
    if (scopes.size === 1) {
      issues.push(
        `${hook}: shared by ${owned.length} same-scope rules (${owned.join(", ")}) — ` +
          "split a new rule + hook pair per validation domain (omp-hooks.md 1:1 separation)",
      );
    }
  }

  // Mapped rules must exist on disk (dangling mapping).
  // RULES.md is the sticky rule at .omp/RULES.md — not under .omp/rules/.
  for (const ruleFile of mappedRules) {
    const rulePath = ruleFile === "RULES.md" ? join(ompDir, "RULES.md") : join(rulesDir, ruleFile);
    if (!existsSync(rulePath)) {
      issues.push(`mapping references '${ruleFile}' but the rule file does not exist`);
    }
  }

  return issues;
}

/**
 * A warning the agent cannot act on is a warning that costs context for
 * nothing. `main.py: CORS missing` sends the reader to one file; `CORS missing`
 * sends it to grep the tree. Interpolated messages carry their subject in the
 * template (`${file}: ...`), so only fully literal strings can be checked — and
 * those are exactly the ones that used to describe a missing construct without
 * naming the file that must contain it.
 */
function checkIssuesNameTheirPlace(): string[] {
  const issues: string[] = [];
  const place = /[\w.@-]+\.(py|ts|tsx|md|http|yml|json|css|mjs|sh|example)\b|[\w.@-]+\//;
  for (const dir of ["post", "lib"]) {
    const dirPath = join(ompDir, "hooks", dir);
    if (!existsSync(dirPath)) continue;
    for (const file of readdirSync(dirPath)) {
      if (!file.endsWith(".ts") || file.endsWith(".d.ts")) continue;
      const source = stripComments(readFileSync(join(dirPath, file), "utf-8"));
      for (const push of source.matchAll(/issues\.push\(\s*("(?:[^"\\]|\\.)*")/g)) {
        if (place.test(push[1])) continue;
        issues.push(
          `${dir}/${file}: warning ${push[1].slice(0, 60)} names no file or directory — ` +
            "prefix the path it applies to, or the agent has to search for it",
        );
      }
    }
  }
  return issues;
}

/**
 * Rule files whose frontmatter carries a TTSR `condition`. They are delivery
 * mechanisms for an invariant a hook already owns, so they never count toward
 * the one-domain-per-hook split heuristic.
 */
function listTtsrRules(rulesDir: string): Set<string> {
  const ttsr = new Set<string>();
  if (!existsSync(rulesDir)) return ttsr;
  for (const file of readdirSync(rulesDir)) {
    if (!file.endsWith(".md")) continue;
    const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---/.exec(readFileSync(join(rulesDir, file), "utf-8"));
    if (frontmatter === null) continue;
    if (/^condition:\s*\S/m.test(frontmatter[1])) ttsr.add(file);
  }
  return ttsr;
}

// Direct execution (make check-omp-hooks): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-omp-hooks.ts")) {
  const issues = checkOmpHooksSync();
  console.log("==> check-omp-hooks");
  if (issues.length === 0) {
    console.log("    PASS: .omp/hooks/ structure + hook functional contract valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-omp-hooks");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
