/**
 * check-harness — 하네스 자기 검증. 규칙 ↔ 검사 ↔ Makefile ↔ settings.json 의 이름 계약.
 *
 * 규칙: .claude/rules/harness.md
 *  - `.claude/rules/<name>.md` 마다 `.claude/hooks/check-<name>.ts`, 역방향도 성립
 *  - 규칙 프런트매터: `paths` 비어 있지 않은 리스트, 각 glob 이 레포의 실재 파일과 1개 이상 매치. 본문 H1
 *  - Makefile: `check-<name>` 타깃의 레시피는 `node .claude/hooks/check-<name>.ts`, `## ` 설명, .PHONY 등재,
 *    `verify` 의 선행 조건 == 모든 check-* 타깃
 *  - settings.json: PreToolUse(Bash → pre-bash.ts, Edit|Write → pre-write.ts), PostToolUse(Edit|Write → post-edit.ts).
 *    hooks/ 의 pre-·post- 스크립트는 전부 등록돼 있고, 등록된 명령 파일은 실재
 *  - hooks/ 아래는 .ts 만(도구 언어 하나). 셸·파이썬 금지
 *  - 훅 스모크: pre-bash 가 금지 명령을 deny 하고, pre-write 가 bench/ 하위 디렉터리를 deny 하고, post-edit 가 죽지 않는다
 */
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { type Check, type Issue, globToRegExp, isMain, listFiles, parseFrontmatter, read, runCli } from "./lib/harness.ts";

const HOOK_WIRING: Array<{ event: string; matcher: string; file: string }> = [
  { event: "PreToolUse", matcher: "Bash", file: "pre-bash.ts" },
  { event: "PreToolUse", matcher: "Edit|Write", file: "pre-write.ts" },
  { event: "PostToolUse", matcher: "Edit|Write", file: "post-edit.ts" },
];

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const rules = listFiles(root, ".claude/rules").filter((f) => f.endsWith(".md")).map((f) => f.slice(0, -3));
  const hooks = listFiles(root, ".claude/hooks");
  const checks = hooks.filter((f) => /^check-.+\.ts$/.test(f)).map((f) => f.slice(6, -3));

  // --- 규칙 ↔ 검사 ---
  for (const r of rules) if (!checks.includes(r)) issues.push(`.claude/rules/${r}.md 에 대응하는 .claude/hooks/check-${r}.ts 가 없다`);
  for (const c of checks) if (!rules.includes(c)) issues.push(`.claude/hooks/check-${c}.ts 에 대응하는 .claude/rules/${c}.md 가 없다`);
  for (const f of hooks) if (!f.endsWith(".ts")) issues.push(`.claude/hooks/${f}: 훅·검사는 TypeScript 만 쓴다`);
  for (const f of listFiles(root, ".claude/hooks/lib")) if (!f.endsWith(".ts")) issues.push(`.claude/hooks/lib/${f}: TypeScript 만`);

  // --- 규칙 프런트매터 ---
  const repoFiles = walk(root);
  for (const r of rules) {
    const rel = `.claude/rules/${r}.md`;
    const fm = parseFrontmatter(read(root, rel) ?? "");
    if (!fm) { issues.push(`${rel}: 프런트매터가 없다`); continue; }
    const paths = fm.data.paths;
    if (!Array.isArray(paths) || paths.length === 0) issues.push(`${rel}: paths 가 비어 있다`);
    else for (const g of paths as string[]) {
      const re = globToRegExp(g);
      if (!repoFiles.some((f) => re.test(f))) issues.push(`${rel}: paths "${g}" 에 매치되는 파일이 없다`);
    }
    if (!/^# .+/m.test(fm.body)) issues.push(`${rel}: 본문 H1 제목이 없다`);
    if (!fm.body.includes(`check-${r}`)) issues.push(`${rel}: 본문이 검사 이름(make check-${r})을 적지 않는다`);
  }

  // --- Makefile ---
  const mk = read(root, "Makefile");
  if (mk === null) issues.push("Makefile 이 없다");
  else {
    const phony = new Set((mk.match(/^\.PHONY:(.*)$/m)?.[1] ?? "").trim().split(/\s+/).filter(Boolean));
    const targets = [...mk.matchAll(/^([a-zA-Z][\w-]*):([^=\n]*?)(?:\s*## (.*))?$/gm)].map((m) => ({ name: m[1], deps: m[2].trim().split(/\s+/).filter(Boolean), doc: m[3] }));
    const byName = new Map(targets.map((t) => [t.name, t]));
    for (const t of targets) {
      if (!phony.has(t.name)) issues.push(`Makefile: ${t.name} 이 .PHONY 에 없다`);
      if (!t.doc) issues.push(`Makefile: ${t.name} 에 '## 설명' 이 없다`);
    }
    for (const p of phony) if (!byName.has(p)) issues.push(`Makefile: .PHONY 의 ${p} 타깃이 없다`);
    for (const c of checks) {
      const t = byName.get(`check-${c}`);
      if (!t) { issues.push(`Makefile: check-${c} 타깃이 없다`); continue; }
      const recipe = mk.match(new RegExp(`^check-${escape(c)}:.*\\n((?:\\t.*\\n?)+)`, "m"))?.[1] ?? "";
      if (!recipe.includes(`node .claude/hooks/check-${c}.ts`)) issues.push(`Makefile: check-${c} 레시피가 'node .claude/hooks/check-${c}.ts' 가 아니다`);
    }
    const verify = byName.get("verify");
    if (!verify) issues.push("Makefile: verify 타깃이 없다");
    else {
      const want = checks.map((c) => `check-${c}`).sort(), have = [...verify.deps].sort();
      if (want.join(" ") !== have.join(" ")) issues.push(`Makefile: verify 의 선행 조건이 모든 check-* 와 다르다 — 기대 [${want.join(" ")}], 실제 [${have.join(" ")}]`);
    }
    for (const t of targets) if (t.name.startsWith("check-") && !checks.includes(t.name.slice(6))) issues.push(`Makefile: ${t.name} 에 대응하는 검사 파일이 없다`);
  }

  // --- settings.json ---
  const st = read(root, ".claude/settings.json");
  if (st === null) issues.push(".claude/settings.json 이 없다");
  else {
    let cfg: Record<string, unknown> = {};
    try { cfg = JSON.parse(st); } catch (e) { issues.push(`.claude/settings.json: JSON 파싱 실패 — ${(e as Error).message}`); }
    const hooksCfg = (cfg.hooks ?? {}) as Record<string, Array<{ matcher?: string; hooks?: Array<{ type?: string; command?: string; timeout?: number }> }>>;
    const registered = new Set<string>();
    for (const [event, entries] of Object.entries(hooksCfg)) for (const e of entries ?? []) for (const h of e.hooks ?? []) {
      const m = h.command?.match(/\.claude\/hooks\/([\w.-]+\.ts)/);
      if (!m) { issues.push(`.claude/settings.json ${event}: 명령이 .claude/hooks/*.ts 가 아니다(${h.command})`); continue; }
      registered.add(`${event}|${e.matcher ?? ""}|${m[1]}`);
      if (!existsSync(join(root, ".claude/hooks", m[1]))) issues.push(`.claude/settings.json ${event}: ${m[1]} 이 없다`);
      if (!h.command?.includes("$CLAUDE_PROJECT_DIR")) issues.push(`.claude/settings.json ${event}: 명령은 $CLAUDE_PROJECT_DIR 기준 절대 경로여야 한다`);
      if (typeof h.timeout !== "number") issues.push(`.claude/settings.json ${event} ${m[1]}: timeout(초) 을 명시한다`);
    }
    for (const w of HOOK_WIRING) {
      if (!registered.has(`${w.event}|${w.matcher}|${w.file}`)) issues.push(`.claude/settings.json: ${w.event} matcher "${w.matcher}" → ${w.file} 등록이 없다`);
    }
    for (const f of hooks.filter((f) => /^(pre|post)-.+\.ts$/.test(f))) {
      if (![...registered].some((r) => r.endsWith(`|${f}`))) issues.push(`.claude/hooks/${f} 가 settings.json 에 등록돼 있지 않다`);
    }
  }

  // --- 스모크 ---
  issues.push(...smoke(root));
  return issues;
}

function smoke(root: string): Issue[] {
  const out: Issue[] = [];
  const run = (file: string, input: object): { code: number; stdout: string; stderr: string } => {
    try {
      const stdout = execFileSync("node", [join(root, ".claude/hooks", file)], { input: JSON.stringify(input), cwd: root, encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"], env: { ...process.env, CLAUDE_PROJECT_DIR: root } });
      return { code: 0, stdout, stderr: "" };
    } catch (e) {
      const err = e as { status?: number; stdout?: string; stderr?: string };
      return { code: err.status ?? -1, stdout: String(err.stdout ?? ""), stderr: String(err.stderr ?? "") };
    }
  };
  const deny = (r: { code: number; stdout: string }): boolean => r.code === 0 && /"permissionDecision"\s*:\s*"deny"/.test(r.stdout);
  const askUp = (r: { code: number; stdout: string }): boolean => r.code === 0 && /"permissionDecision"\s*:\s*"ask"/.test(r.stdout);
  if (existsSync(join(root, ".claude/hooks/pre-bash.ts"))) {
    if (!deny(run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "brew services start ollama" } }))) out.push("스모크: pre-bash 가 'brew services start ollama' 를 deny 하지 않는다");
    if (!deny(run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "brew services restart jundot/omlx/omlx" } }))) out.push("스모크: pre-bash 가 'brew services restart jundot/omlx/omlx' 를 deny 하지 않는다");
    if (!askUp(run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "git commit -m 'x'" } }))) out.push("스모크: pre-bash 가 'git commit' 을 ask 로 올리지 않는다(규칙 8)");
    if (!askUp(run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "cd /tmp && git push origin main" } }))) out.push("스모크: pre-bash 가 'git push' 를 ask 로 올리지 않는다(규칙 8)");
    const ok = run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "ollama ps" } });
    if (ok.code !== 0 || /deny/.test(ok.stdout)) out.push("스모크: pre-bash 가 'ollama ps' 를 막는다");
    const okGit = run("pre-bash.ts", { tool_name: "Bash", tool_input: { command: "git status --porcelain && git diff" } });
    if (okGit.code !== 0 || /"(deny|ask)"/.test(okGit.stdout)) out.push("스모크: pre-bash 가 읽기용 git(status/diff)을 막는다");
  }
  if (existsSync(join(root, ".claude/hooks/pre-write.ts"))) {
    if (!deny(run("pre-write.ts", { tool_name: "Write", tool_input: { file_path: join(root, "bench/results/x.md"), content: "" } }))) out.push("스모크: pre-write 가 bench/results/ 를 deny 하지 않는다");
    const ok = run("pre-write.ts", { tool_name: "Write", tool_input: { file_path: join(root, "bench/2026-01-01.s1.x.md"), content: "" } });
    if (ok.code !== 0 || /deny/.test(ok.stdout)) out.push("스모크: pre-write 가 표준 파일명을 막는다");
  }
  if (existsSync(join(root, ".claude/hooks/post-edit.ts"))) {
    const r = run("post-edit.ts", { tool_name: "Edit", tool_input: { file_path: join(root, "ollama/Modelfile.qwen3.6-coder") } });
    if (r.code !== 0 && r.code !== 2) out.push(`스모크: post-edit 가 비정상 종료(${r.code}): ${r.stderr.split("\n")[0]}`);
  }
  return out;
}

function walk(root: string): string[] {
  const out: string[] = [];
  const skip = new Set([".git", "sandbox", "node_modules"]);
  const rec = (rel: string) => {
    for (const e of readdirSync(join(root, rel))) {
      if (rel === "" && skip.has(e)) continue;
      const r = rel ? `${rel}/${e}` : e;
      if (statSync(join(root, r)).isDirectory()) rec(r); else out.push(r);
    }
  };
  rec("");
  return out;
}

function escape(s: string): string { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

export const check: Check = { name: "check-harness", run };
if (isMain(import.meta.url)) runCli(check);
