import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { createHash } from "node:crypto";
// @ts-expect-error — Node builtin, not project-compiled
import { execFileSync } from "node:child_process";
import { touchesStrict } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

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
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


/** Keep the always-apply set tiny: each such rule injects full content every session. */
const MAX_ALWAYS_APPLY = 2;

export default function checkOmpRules(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-omp-rules", event, () => {
    // Skip read-only tools — they cannot change .omp/ files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesStrict(event, [".omp/"])) return;

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
    issues.push(...checkProcedureSections(file, content));
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
/**
 * How-to 절은 순서+검증 구조여야 한다 (2026-09-01, omp-conventions "ordered-verified").
 * 실측: 산출물 목록뿐이던 도메인 절차가 이 구조가 되자 풀스택 셀이 TO→초록으로 넘어갔다
 * (종반 red 3부류 재현 0). 기계 최소치만 강제한다 — 제목이 절차형(Add/Creat/Build/New/추가)
 * 인 ## 절은 (a) 순서 목록(`1.`)을 갖고 (b) 검증 참조(make 타깃·pytest·rule://·check-)를
 * 최소 1개 담는다. 단계별 검증의 "충분함"은 기계가 못 재니 저작 표준(문서)이 담당한다.
 */
function checkProcedureSections(file: string, body: string): string[] {
  const issues: string[] = [];
  for (const sec of body.split(/^## /m).slice(1)) {
    const title = sec.split("\n", 1)[0].trim();
    if (!/\b(Add(ing)?|Creat(e|ing)|Build|New [A-Z])\b|추가할 때|만들 때/.test(title)) continue;
    const secBody = sec.slice(title.length);
    if (!/^\s*\d+\.\s/m.test(secBody)) {
      issues.push(`${file}: "## ${title}" — 절차 절인데 순서 목록이 없다. 산출물 나열이 아니라 순서 있는 단계로 쓴다 (omp-conventions, ordered-verified)`);
    }
    if (!/make [a-z][\w-]+|pytest|rule:\/\/|check-[a-z-]+/.test(secBody)) {
      issues.push(`${file}: "## ${title}" — 절차 절에 검증 참조가 하나도 없다. 각 단계가 어느 검사/타깃으로 서는지 명시한다 (omp-conventions, ordered-verified)`);
    }
  }
  return issues;
}

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
  if (Array.isArray(scope)) {
    // omp 는 YAML 리스트 scope 도 받는다(실측 2026-08-31, ttsr test 발화 확인) — 하지만 이
    // 하네스는 문자열 한 줄로 표준화한다: liveness 파서와 사람이 한 형태만 읽으면 된다.
    issues.push(
      `${file}: 'scope' is a YAML list — omp accepts it, but this harness standardizes on the ` +
        `single comma-separated string form: scope: "${(scope as unknown[]).join(", ")}"`,
    );
  } else if (typeof scope !== "string" || scope.trim() === "") {
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
  if (typeof scope === "string") issues.push(...checkTriggerLiveness(file, body, String(condition), scope));
  return issues;
}

/**
 * 각 스코프 스트림마다 condition 이 **실제로 매치되는 표본**을 본문에 요구한다:
 *
 *   <!-- fires-on tool:bash: make migrate-gen -->
 *   <!-- fires-on tool:edit(backend/app/routers/*.py): x: str = Depends(get_x) -->
 *
 * 근거(2026-08-31 실측): condition 을 명령 모양(`alembic\s+revision`)으로 좁히면서
 * scope 에 tool:write(backend/alembic/versions/*.py) 를 더한 편집이 있었다 — 그 스트림이
 * 나르는 것(경로·파일 내용)에는 그 정규식이 매치될 수 없어 **죽은 스트림**이었고, 이
 * 검사의 기존 항목은 전부 통과했다. 죽음의 완전 판정은 기계로 불가능하다(금지 토큰
 * 규칙은 트리 매치 0 이 정상이다) — 그래서 가드를 프루프로 고정하듯, 스트림마다 저자가
 * 매치 표본을 대게 하고 여기서 정규식을 실제로 대 본다. 표본을 만들 수 없는 스트림은
 * 그 자리에서 죽은 것으로 드러난다.
 */
function checkTriggerLiveness(file: string, body: string, condition: string, scope: string): string[] {
  const issues: string[] = [];
  const pattern = safeRegExp(condition);
  if (pattern === null) return issues;
  // edit/write 쌍은 같은 내용을 나른다 — 표본 키는 glob(괄호 안), 경로 없는 스트림은 그대로.
  const keyOf = (stream: string): string => /\(([^)]+)\)/.exec(stream)?.[1]?.trim() ?? stream;
  const samples = new Map<string, string>();
  for (const m of body.matchAll(/<!--\s*fires-on\s+([^:]+(?::bash|:eval)?):\s*(.+?)\s*-->/g)) {
    samples.set(keyOf(m[1].trim()), m[2]);
  }
  for (const stream of scope.split(",").map((x) => x.trim()).filter(Boolean)) {
    const sample = samples.get(keyOf(stream));
    if (sample === undefined) {
      issues.push(
        `${file}: scope stream '${stream}' has no liveness sample — add ` +
          `\`<!-- fires-on ${keyOf(stream)}: <text the condition matches on this stream> -->\` to the body ` +
          "(one sample per glob covers its edit/write pair). " +
          "A stream you cannot write a sample for is a stream the condition can never fire on.",
      );
      continue;
    }
    if (!new RegExp(pattern.source).test(sample)) {
      issues.push(
        `${file}: liveness sample for '${stream}' ("${sample.slice(0, 48)}") does not match the ` +
          "condition — the sample or the regex is wrong, and until they agree the stream is unproven",
      );
    }
  }
  issues.push(...engineLiveness(file, condition, scope, samples, keyOf));
  return issues;
}

/**
 * 정규식 플로어 위에 **omp 실엔진 검증**을 얹는다 — `omp ttsr test --rule` 은 우리 JS 재구현이
 * 못 보는 것(glob 라우팅, 소스 구분, 직렬화)까지 실제 매칭 경로로 판정한다. 실측(2026-08-31):
 * JS 검증을 통과한 crash-guard 표본이 직렬화형(\") 에선 엔진 무발화였다.
 *
 * 비용 제어: 호출당 ~0.3s 라 glob 당 대표 스트림 1회만 돌리고, 결과를 규칙 내용 해시로
 * `.omp/state/ttsr-liveness-cache.json` 에 캐시한다 — 규칙이 안 바뀌면 엔진 호출 0.
 * 따옴표 든 condition 은 표본의 JSON 직렬화 변형도 함께 대 본다(스트리밍 직렬화 내성).
 * omp CLI 가 없는 호스트는 정규식 플로어만으로 통과시킨다(fail-open, stderr 에 한 줄).
 */
function engineLiveness(
  file: string,
  condition: string,
  scope: string,
  samples: Map<string, string>,
  keyOf: (s: string) => string,
): string[] {
  const issues: string[] = [];
  const rulePath = join(cwd, ".omp", "rules", file);
  let ruleText: string;
  try { ruleText = readFileSync(rulePath, "utf-8"); } catch { return issues; }
  const hash = createHash("sha256").update(ruleText).digest("hex").slice(0, 16);
  const cachePath = join(cwd, ".omp", "state", "ttsr-liveness-cache.json");
  let cache: Record<string, string[]> = {};
  try { cache = JSON.parse(readFileSync(cachePath, "utf-8")) as Record<string, string[]>; } catch { /* 첫 실행 */ }
  const cacheKey = `${file}@${hash}`;
  if (cacheKey in cache) return cache[cacheKey];

  const seen = new Set<string>();
  for (const stream of scope.split(",").map((x) => x.trim()).filter(Boolean)) {
    const key = keyOf(stream);
    if (seen.has(key)) continue; // edit/write 쌍은 같은 내용을 나른다 — glob 당 1회
    seen.add(key);
    const sample = samples.get(key);
    if (sample === undefined) continue; // 표본 부재는 위에서 이미 이슈다
    const args = ["ttsr", "test", "--json", "--rule", rulePath];
    const m = /^tool:(\w+)(?:\(([^)]+)\))?$/.exec(stream);
    if (m) {
      args.push("--source", "tool", "--tool", m[1]);
      if (m[2]) args.push("--path", m[2].trim().replace(/\*\*\//g, "x/").replace(/\*\*/g, "x").replace(/\*/g, "sample"));
    } else {
      args.push("--source", stream); // text | thinking
    }
    const variants = [sample];
    if (/["']/.test(condition)) variants.push(JSON.stringify(sample).slice(1, -1)); // 직렬화형
    for (const v of variants) {
      let out: string;
      try {
        out = execFileSync("omp", [...args, v], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], timeout: 15000 });
      } catch {
        console.error("check-omp-rules: omp CLI 실행 불가 — 엔진 liveness 는 건너뜀(정규식 플로어만 적용)");
        return issues;
      }
      let fired = false;
      try { fired = ((JSON.parse(out) as { triggered?: unknown[] }).triggered ?? []).length > 0; } catch { /* 파싱 실패 = 미발화로 본다 */ }
      if (!fired) {
        issues.push(
          `${file}: omp 엔진에서 '${stream}' 표본${v === sample ? "" : "(직렬화형)"} 이 발화하지 않는다 — ` +
            `\`omp ttsr test --rule .omp/rules/${file} ${args.slice(5).join(" ")} '${v.slice(0, 40)}'\` 로 재현. ` +
            "정규식은 맞는데 엔진이 침묵하면 scope 라우팅이나 직렬화 문제다",
        );
      }
    }
  }
  cache[cacheKey] = issues;
  try { mkdirSync(join(cwd, ".omp", "state"), { recursive: true }); writeFileSync(cachePath, JSON.stringify(cache)); } catch { /* 캐시 실패는 무해 */ }
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
  printRuleHint("check-omp-rules");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
