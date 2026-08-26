import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";

/**
 * Check-Omp-Rules Post Hook
 *
 * After tool execution, verifies the dynamic rule-loading contract:
 *   1. AGENTS.md must NOT import .omp/rules/*.md via @rules/ — rules load
 *      dynamically as rulebook entries (name + globs + description in the
 *      system prompt, content on demand via rule://<name>). @rules/ imports
 *      inject full content into every session and defeat on-demand loading.
 *   2. No .omp/rules/RULES.md — it shadows the sticky RULES.md.
 *   3. Every rule file has valid frontmatter: description, globs, alwaysApply=false.
 *   4. The alwaysApply: true set stays tiny — full content injects every session.
 *   5. File naming: <scope>-<name>.md with a known prefix (backend-, frontend-,
 *      omp-, root-) per omp-conventions.md "Directory Naming".
 *
 * This is a read-only check — it does NOT block tool calls.
 * To add a rule: create .omp/rules/<scope>-<name>.md with frontmatter only.
 * To validate: run `make check-omp-rules` (part of `make verify`).
 */
const cwd = process.cwd();
const ompDir = join(cwd, ".omp");
const agentsPath = join(ompDir, "AGENTS.md");
const rulesDir = join(ompDir, "rules");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


/** Keep the always-apply set tiny: each such rule injects full content every session. */
const MAX_ALWAYS_APPLY = 2;

export default function checkOmpRules(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-omp-rules", event, () => {
    // Skip read-only tools — they cannot change .omp/ files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkOmpRulesSync();
    if (issues.length === 0) {
      resetSuppression("check-omp-rules"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-omp-rules",
      issues,
      "run make check-omp-rules for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-omp-rules") };
  }));
}

function checkOmpRulesSync(): string[] {
  const issues: string[] = [];

  // Check 1: AGENTS.md must not import rules via @rules/ (breaks dynamic loading)
  if (existsSync(agentsPath)) {
    const agentsContent = readFileSync(agentsPath, "utf-8");
    const refPattern = /^@rules\/(\S+\.md)/gm;
    let m: RegExpExecArray | null;
    while ((m = refPattern.exec(agentsContent)) !== null) {
      issues.push(
        `AGENTS.md imports @rules/${m[1]} — remove it; rules load dynamically via the rulebook (rule://<name>)`,
      );
    }
  }

  if (!existsSync(rulesDir)) {
    issues.push(".omp/rules/ directory not found");
    return issues;
  }

  const ruleFiles = readdirSync(rulesDir).filter((f: string) => f.endsWith(".md"));

  // Check 2: no rules/RULES.md — native regular rules load earlier and shadow sticky RULES.md
  if (ruleFiles.includes("RULES.md")) {
    issues.push(".omp/rules/RULES.md shadows the sticky RULES.md — rename it");
  }

  // Check 2b: file naming — <scope>-<name>.md with a known scope prefix
  // (per omp-conventions.md "Directory Naming"). RULES.md is the sticky
  // exception, already flagged above. Cross-cutting rules (globs spanning
  // multiple top-level dirs, e.g. environment.md covering root + backend)
  // omit the prefix.
  const knownPrefixes = ["backend-", "frontend-", "omp-", "root-"];
  for (const file of ruleFiles) {
    if (file === "RULES.md") continue;
    const content = readFileSync(join(rulesDir, file), "utf-8");
    const fm = parseFrontmatter(content);
    const globs = Array.isArray(fm?.["globs"]) ? (fm["globs"] as string[]) : [];
    // Top-level dir of each glob: `.omp/...` → `.omp`, `backend/...` → `backend`.
    const topDirs = new Set(globs.map((g) => (g.startsWith(".omp") ? ".omp" : g.split("/")[0])));
    const isTtsr = typeof fm?.["condition"] === "string" && (fm["condition"] as string).trim() !== "";

    if (knownPrefixes.some((p) => file.startsWith(p))) {
      // Check 2c: prefix ↔ globs consistency (omp-naming-consistency.md).
      // A scoped rule must have at least one glob in its scope's top-level dir.
      // TTSR rules (condition-triggered, no globs by design) are exempt.
      const prefix = knownPrefixes.find((p) => file.startsWith(p))!;
      if (isTtsr) continue;
      // `omp-` prefix governs the `.omp/` directory; others map 1:1.
      const expectedDir = prefix === "root-" ? null : prefix === "omp-" ? ".omp" : prefix.replace(/-$/, "");
      if (expectedDir === null) {
        // root- rules govern root-level files (Makefile, docker-compose.yml, .env*)
        const rootFiles = globs.filter((g) => !g.includes("/"));
        if (rootFiles.length === 0) {
          issues.push(
            `${file}: root- rule must have at least one root-level glob ` +
              `(Makefile, docker-compose.yml, .env*) — see omp-naming-consistency.md`,
          );
        }
      } else if (!topDirs.has(expectedDir)) {
        issues.push(
          `${file}: ${prefix} rule has no glob under ${expectedDir}/ — ` +
            `name says ${prefix} but globs govern ${[...topDirs].join(", ") || "(none)"} — ` +
            "see omp-naming-consistency.md",
        );
      }
      continue;
    }

    // Prefix-less is allowed only when globs span multiple top-level dirs.
    if (topDirs.size <= 1) {
      issues.push(
        `${file}: filename must be <scope>-<name>.md with a known prefix ` +
          `(${knownPrefixes.join(", ")}) — see omp-conventions.md "Directory Naming"`,
      );
    }
  }

  // Check 3: frontmatter validation
  let alwaysApplyCount = 0;
  for (const file of ruleFiles) {
    const filePath = join(rulesDir, file);
    const content = readFileSync(filePath, "utf-8");
    const fm = parseFrontmatter(content);

    if (!fm) {
      issues.push(`${file}: missing frontmatter (--- ... ---)`);
      continue;
    }
    const desc = fm["description"];
    if (typeof desc !== "string" || desc.trim() === "") {
      issues.push(`${file}: missing or empty 'description' in frontmatter`);
    }
    const globs = fm["globs"];
    const condition = fm["condition"];
    const isTtsr = typeof condition === "string" && condition.trim() !== "";
    // globs are optional for TTSR rules: a glob gate requires file paths in
    // the match context, which bash tool calls never provide — so a globbed
    // TTSR rule would never trigger on `make migrate` etc.
    if (!isTtsr && (!Array.isArray(globs) || globs.length === 0)) {
      issues.push(`${file}: missing or empty 'globs' in frontmatter`);
    }
    if (fm["alwaysApply"] === true || fm["alwaysApply"] === "true") {
      alwaysApplyCount += 1;
    } else if (fm["alwaysApply"] !== false && fm["alwaysApply"] !== "false") {
      issues.push(`${file}: 'alwaysApply' must be false (got ${String(fm["alwaysApply"])})`);
    }
    issues.push(...checkTtsrTrigger(file, content, fm));
  }

  // Check 4: keep the always-apply set tiny
  if (alwaysApplyCount > MAX_ALWAYS_APPLY) {
    issues.push(
      `${alwaysApplyCount} rule(s) set alwaysApply: true (max ${MAX_ALWAYS_APPLY}) — full content injects into every session; prefer rulebook (rule://<name>) or RULES.md`,
    );
  }

  // Check 5: stale port literals. sandbox 포트는 전부 1-프리픽스(18000/15173/15432/16379…)다.
  // fast-api-standard 원본 포트(8000 등)가 룰 본문에 남으면 훅과 문서가 어긋난다 —
  // 실측: backend-api-http.md 가 "port other than 8000" 을 남겨 훅(:18000 강제)과 모순됐다.
  // Stale-port set is derived from docker-compose port mappings ("1XXXX:XXXX"):
  // every internal port whose host side is its 1-prefixed twin is a legacy port
  // that must not appear host-side in rule text. Falls back to the known set.
  let stalePortList = ["8000", "5173", "5432", "6379", "6006", "4317"];
  try {
    const compose = readFileSync(join(cwd, "docker-compose.yml"), "utf-8");
    const derived = [...compose.matchAll(/"1(\d{3,4}):(\d{3,4})"/g)]
      .filter((mm) => mm[1] === mm[2]).map((mm) => mm[2]);
    if (derived.length) stalePortList = [...new Set([...stalePortList, ...derived])];
  } catch { /* compose 없음 — 정적 목록 유지 */ }
  const STALE_PORTS = new RegExp(`(?<!\\d)(${stalePortList.join("|")})(?!\\d)`);
  for (const file of ruleFiles) {
    // 컨테이너 간 DSN(`@postgres:5432` 등)은 도커 내부 포트라 정당 — 호스트쪽 포트만 감사한다.
    const content = readFileSync(join(rulesDir, file), "utf-8")
      .replace(new RegExp(`(?:@|//)[a-z][a-z0-9_-]*:(?:${stalePortList.join("|")})\\b`, "g"), "@svc:INTERNAL");
    const m = STALE_PORTS.exec(content);
    if (m) {
      issues.push(
        `${file}: stale port ${m[1]} — sandbox ports are 1-prefixed (1${m[1]}); ` +
          "update the rule text to match the harness",
      );
    }
  }

  // Check 6: ghost <Name>Service references. 룰이 예시로 든 서비스는 실제 도메인이어야 한다 —
  // 실측: backend-testing.md 가 ItemService/TodoService/TaskService(존재하지 않는 도메인)를
  // 표준 표에 실어 모델을 유령 구조로 안내했다. 플레이스홀더(Name/X)와 실재 도메인만 허용.
  const modelsDir = join(cwd, "backend", "app", "models");
  const domainAllow = new Set<string>(["name", "x", "xxx", "user", "integration", "example", "sample", "demo", "foo"]);
  try {
    for (const f of readdirSync(modelsDir)) {
      if (f.endsWith(".py") && f !== "__init__.py") domainAllow.add(f.slice(0, -3).toLowerCase());
    }
  } catch { /* models 디렉터리 없음 — 스킵 */ }
  for (const file of ruleFiles) {
    if (!file.startsWith("backend-")) continue;
    const content = readFileSync(join(rulesDir, file), "utf-8");
    const seen = new Set<string>();
    for (const mm of content.matchAll(/\b([A-Z][A-Za-z0-9]*)Service\b/g)) {
      const base = mm[1].toLowerCase();
      if (domainAllow.has(base) || seen.has(base)) continue;
      seen.add(base);
      issues.push(
        `${file}: ghost reference \`${mm[1]}Service\` — no backend/app/models/${base}.py; ` +
          "examples must use real domains or the Name/X placeholder",
      );
    }
  }

  // Check 7: reference-snippet drift. When a rule declares "`<path>` is the reference"
  // and prints a code fence, every meaningful fence line must exist in that file —
  // measured: backend-domain.md printed a models/batch.py snippet without String(120)
  // and the layout banners, so copying the "reference" failed two hooks.
  for (const file of ruleFiles) {
    const content = readFileSync(join(rulesDir, file), "utf-8");
    const refRe = /`([\w./-]+\.(?:py|ts|tsx|js|mjs|md|yml|yaml|toml|json|http))`[^\n]{0,40}\breference\b[\s\S]{0,200}?```[a-z]*\n([\s\S]*?)```/g;
    for (const m of content.matchAll(refRe)) {
      const refPath = join(cwd, "backend", "app", m[1].replace(/^backend\/app\//, ""));
      const realPath = existsSync(refPath) ? refPath : join(cwd, m[1]);
      if (!existsSync(realPath)) continue;
      const real = readFileSync(realPath, "utf-8").replace(/\s+/g, " ");
      for (const line of m[2].split("\n")) {
        const t = line.trim();
        if (t === "" || t.startsWith("#") || t.startsWith("...")) continue;
        if (!real.includes(t.replace(/\s+/g, " "))) {
          issues.push(
            `${file}: reference snippet for \`${m[1]}\` drifted — line not in the real file: "${t.slice(0, 70)}" — ` +
              "quote the actual file or drop the reference claim",
          );
          break;
        }
      }
    }
  }

  // Check 8: legacy schema-class tokens. The naming convention is
  // <Name>CreateRequest/<Name>ReadResponse/...Internal — bare XCreate/NameRead
  // style tokens contradict it inside the same rulebook (measured:
  // backend-domain.md said both, and following the legacy half failed the hook).
  const LEGACY = /(?:\b(?:X|Xxx|Name)|<Name>)(?:Create|Read|Update)(?!Request|Response|Internal)\b/;
  for (const file of ruleFiles) {
    if (!file.startsWith("backend-")) continue;
    const content = readFileSync(join(rulesDir, file), "utf-8");
    const m = LEGACY.exec(content);
    if (m) {
      issues.push(
        `${file}: legacy schema token \`${m[0]}\` — the convention is ` +
          "<Name>CreateRequest/<Name>ReadResponse/...Internal; state one naming scheme only",
      );
    }
  }

  return issues;
}

/**
 * A TTSR rule's frontmatter is executable configuration, and every way it can
 * be wrong fails silently at runtime: an invalid regex is skipped with a log
 * warning nobody reads, a `condition` written as a YAML list reads as a
 * non-TTSR rule to this check, and an unstated `scope`/`interruptMode` leaves
 * behaviour to machine-global defaults — a code-token trigger with the default
 * scope also watches assistant prose, so merely *writing about*
 * `HTTPException` would abort the turn.
 */
function checkTtsrTrigger(file: string, body: string, fm: Record<string, unknown>): string[] {
  const issues: string[] = [];
  const condition = fm["condition"];
  if (condition === undefined) return issues;

  if (typeof condition !== "string" || condition.trim() === "") {
    issues.push(
      `${file}: 'condition' must be a non-empty string — a YAML list still registers ` +
        "as TTSR at runtime but reads as a rulebook rule here, so the two disagree",
    );
    return issues;
  }
  try {
    new RegExp(condition);
  } catch (error) {
    issues.push(
      `${file}: 'condition' is not a valid regex (${String(error)}) — ` +
        "the runtime skips it with a warning and the rule never fires",
    );
  }
  const scope = fm["scope"];
  if (typeof scope !== "string" || scope.trim() === "") {
    issues.push(
      `${file}: a TTSR rule must declare 'scope' — without it the trigger also watches ` +
        "assistant prose, so writing about the forbidden token interrupts the turn",
    );
  } else {
    issues.push(...checkTriggerScopeIsClean(file, String(condition), scope));
  }
  if (fm["interruptMode"] === undefined) {
    issues.push(
      `${file}: a TTSR rule must state 'interruptMode' — the global default decides ` +
        "otherwise, so the same rule behaves differently per machine",
    );
  }
  issues.push(...checkTriggerIsDocumented(file, body, String(condition)));
  return issues;
}

/**
 * Every identifier the condition matches on must be named in the body. An
 * interrupting rule injects that body verbatim, so a token nobody documented is
 * a turn spent on a message that does not explain what stopped the edit — and a
 * silently widened regex is how a trigger starts firing on legitimate code.
 *
 * Tokens are the ≥4-character word runs of the pattern, which drops regex noise
 * (`\b`, `\s*`, `[\w.]`) without having to parse the regex.
 */
function checkTriggerIsDocumented(file: string, body: string, condition: string): string[] {
  const issues: string[] = [];
  if (!/^## Enforcement$/m.test(body)) {
    issues.push(
      `${file}: a TTSR trigger must carry an "## Enforcement" section naming the hook ` +
        "that proves the same invariant after the edit lands",
    );
  }
  for (const token of new Set(condition.split(/[^\w]+/).filter((part) => part.length >= 4))) {
    if (body.includes(token)) continue;
    issues.push(
      `${file}: condition matches on "${token}" but the body never mentions it — ` +
        "the injected text has to explain the token that stopped the edit",
    );
  }
  return issues;
}

/**
 * A trigger that already matches the tree is a trigger that fires when a
 * legitimate line is rewritten. Either the code violates the rule (the owning
 * hook says so) or the regex is too broad; both are the author's problem, not
 * the next session's interrupted turn.
 */
function checkTriggerScopeIsClean(file: string, condition: string, scope: string): string[] {
  const issues: string[] = [];
  const pattern = safeRegExp(condition);
  if (pattern === null) return issues;
  const globs = new Set(
    [...scope.matchAll(/tool:\w+\(([^)]+)\)/g)].map((match: string[]) => match[1].trim()),
  );
  for (const glob of globs) {
    for (const candidate of filesMatching(glob)) {
      const lines = readFileSync(candidate, "utf-8").split(/\r?\n/);
      for (const [index, line] of lines.entries()) {
        if (!pattern.test(line)) continue;
        issues.push(
          `${file}: condition already matches ${candidate.replace(`${cwd}/`, "")}:${index + 1} ` +
            `("${line.trim().slice(0, 48)}") — rewriting that line would interrupt the turn; ` +
            "narrow the regex or fix the code",
        );
        break;
      }
    }
  }
  return issues;
}

/** Files under a `dir/*.ext` or `dir/**` + `/*.ext` glob — the only two forms scopes use. */
function filesMatching(glob: string): string[] {
  const recursive = glob.includes("**");
  const extension = glob.slice(glob.lastIndexOf("."));
  const base = join(cwd, glob.slice(0, glob.indexOf("*")).replace(/\/$/, ""));
  if (!existsSync(base)) return [];
  const found: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (recursive && entry.name !== "__pycache__") walk(full);
        continue;
      }
      if (entry.name.endsWith(extension)) found.push(full);
    }
  };
  walk(base);
  return found;
}

function safeRegExp(source: string): RegExp | null {
  try {
    return new RegExp(source);
  } catch {
    return null;
  }
}

function parseFrontmatter(content: string): Record<string, unknown> | null {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return null;

  const lines = match[1].split(/\r?\n/);
  const result: Record<string, unknown> = {};
  let currentKey = "";
  let listItems: string[] = [];
  let inList = false;

  const flushList = () => {
    if (inList) {
      result[currentKey] = listItems;
      inList = false;
      listItems = [];
    }
  };

  for (const line of lines) {
    const listMatch = line.match(/^\s+-\s+(.+)/);
    if (listMatch && inList) {
      listItems.push(listMatch[1].trim());
      continue;
    }

    const kvMatch = line.match(/^(\w+):\s*(.*)$/);
    if (kvMatch) {
      flushList();
      const [, key, value] = kvMatch;
      if (value === "") {
        currentKey = key;
        inList = true;
        listItems = [];
      } else {
        result[key] = decodeScalar(value.trim());
      }
    }
  }
  flushList();

  return result;
}

/**
 * A quoted YAML scalar decoded the way the runtime's parser sees it: the regex
 * written `condition: "a\\.b"` is the pattern `a\.b`, and validating the raw
 * line instead reports a working pattern as broken.
 */
function decodeScalar(value: string): string {
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1).replaceAll("''", "'");
  }
  if (value.length < 2 || !value.startsWith('"') || !value.endsWith('"')) return value;
  const escapes: Record<string, string> = { "\\": "\\", '"': '"', "/": "/", n: "\n", t: "\t" };
  return value.slice(1, -1).replace(/\\(.)/g, (match: string, char: string) => escapes[char] ?? match);
}

// Direct execution (make check-omp-rules): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-omp-rules.ts")) {
  const issues = checkOmpRulesSync();
  console.log("==> check-omp-rules");
  if (issues.length === 0) {
    console.log("    PASS: no @rules/ imports; .omp/rules/ frontmatter valid, always-apply set tiny");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
