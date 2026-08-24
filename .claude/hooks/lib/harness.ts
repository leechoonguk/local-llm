/**
 * harness.ts — 모든 검사(check-*.ts)와 훅(pre-·post- 스크립트)이 공유하는 공용 모듈.
 *
 * 설계 원칙 (sandbox/.omp/hooks/lib 에서 가져온 것):
 *  - 검사 하나 = 규칙 하나 = Makefile 타깃 하나. 이름은 `.claude/rules/<name>.md`
 *    ↔ `.claude/hooks/check-<name>.ts` ↔ `make check-<name>` 로 일치한다(check-harness 가 강제).
 *  - 검사는 순수 파일 읽기다. 네트워크·서버 상태를 보지 않는다. 훅 실행 시간이 곧 편집 지연이다.
 *  - 검사는 두 모드로 돈다: 독립 실행(`node .claude/hooks/check-x.ts` → 이슈가 있으면 exit 1)과
 *    훅 디스패처(post-edit.ts)가 import 해서 부르는 함수 호출. 어느 쪽이든 이슈는 문자열 배열이다.
 *  - 외부 의존성 없음. YAML 은 이 레포 파일이 쓰는 부분집합만 읽는 자체 파서로 처리한다.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export type Issue = string;
export type Check = { name: string; run: (root: string) => Issue[]; notes?: () => string[] };

// --- 경로 ---------------------------------------------------------------------

/** 레포 루트: $CLAUDE_PROJECT_DIR > 이 파일 기준 상대경로(.claude/hooks/lib → 루트). */
export function repoRoot(): string {
  const env = process.env.CLAUDE_PROJECT_DIR;
  if (env && existsSync(join(env, "CLAUDE.md"))) return resolve(env);
  return resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
}

export function read(root: string, rel: string): string | null {
  const p = join(root, rel);
  return existsSync(p) ? readFileSync(p, "utf-8") : null;
}

export function listFiles(root: string, rel: string): string[] {
  const p = join(root, rel);
  if (!existsSync(p)) return [];
  return readdirSync(p).filter((f) => statSync(join(p, f)).isFile()).sort();
}

export function listDirs(root: string, rel: string): string[] {
  const p = join(root, rel);
  if (!existsSync(p)) return [];
  return readdirSync(p).filter((f) => statSync(join(p, f)).isDirectory()).sort();
}

export function toRel(root: string, abs: string): string {
  return relative(root, resolve(abs)).split("\\").join("/");
}

// --- glob (paths: 프런트매터용 최소 구현) ----------------------------------------
// 지원: `**`(경로 구분자 포함 임의), `*`(구분자 제외 임의), `?`, `{a,b}`. 그 외는 리터럴.

export function globToRegExp(glob: string): RegExp {
  let re = "";
  let i = 0;
  while (i < glob.length) {
    const c = glob[i];
    if (c === "*") {
      if (glob[i + 1] === "*") {
        // `**/` 는 0개 이상의 디렉터리, 끝의 `**` 는 나머지 전부
        if (glob[i + 2] === "/") { re += "(?:.*/)?"; i += 3; } else { re += ".*"; i += 2; }
      } else { re += "[^/]*"; i += 1; }
    } else if (c === "?") { re += "[^/]"; i += 1; }
    else if (c === "{") {
      const end = glob.indexOf("}", i);
      const alts = glob.slice(i + 1, end).split(",").map(escapeRe);
      re += `(?:${alts.join("|")})`; i = end + 1;
    } else { re += escapeRe(c); i += 1; }
  }
  return new RegExp(`^${re}$`);
}

function escapeRe(s: string): string {
  return s.replace(/[.+^$()|[\]\\]/g, "\\$&");
}

export function matchesAny(rel: string, globs: string[]): boolean {
  return globs.some((g) => globToRegExp(g).test(rel));
}

// --- 프런트매터 -----------------------------------------------------------------

export type Frontmatter = { raw: string; data: Record<string, unknown>; body: string } | null;

/** `---\n...\n---\n` 블록을 YAML 부분집합으로 읽는다. 없으면 null. */
export function parseFrontmatter(text: string): Frontmatter {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return null;
  return { raw: m[1], data: parseYaml(m[1]) as Record<string, unknown>, body: m[2] };
}

// --- YAML 부분집합 파서 -----------------------------------------------------------
// 이 레포의 omp/models.yml, config.fragment.yml, 규칙 프런트매터가 쓰는 형태만 지원한다:
// 들여쓰기 기반 맵, `- ` 리스트(스칼라 또는 맵), `#` 주석, 따옴표 키/값, 인라인 `[a, b]`.
// 앵커·멀티라인 스칼라·플로우 맵은 지원하지 않는다 — 나오면 파싱 오류를 이슈로 낸다.

type Y = string | number | boolean | null | Y[] | { [k: string]: Y };

export function parseYaml(text: string): Y {
  const lines = text
    .split(/\r?\n/)
    .map((l, n) => ({ n: n + 1, raw: l, text: stripComment(l) }))
    .filter((l) => l.text.trim() !== "");
  let pos = 0;

  function indentOf(s: string): number { return s.length - s.trimStart().length; }

  function parseBlock(indent: number): Y {
    if (pos >= lines.length) return null;
    const first = lines[pos];
    const ind = indentOf(first.text);
    if (ind < indent) return null;
    if (first.text.trimStart().startsWith("- ")) return parseList(ind);
    return parseMap(ind);
  }

  function parseList(indent: number): Y[] {
    const out: Y[] = [];
    while (pos < lines.length) {
      const l = lines[pos];
      const ind = indentOf(l.text);
      if (ind !== indent || !l.text.trimStart().startsWith("- ")) break;
      const rest = l.text.trimStart().slice(2);
      if (rest.trim() === "") { pos++; out.push(parseBlock(indent + 2)); continue; }
      if (isMapEntry(rest)) {
        // `- key: value` — 항목이 맵. 같은 항목의 다음 키는 indent+2 에 온다.
        lines[pos] = { ...l, text: " ".repeat(indent + 2) + rest };
        out.push(parseMap(indent + 2));
      } else { pos++; out.push(scalar(rest.trim())); }
    }
    return out;
  }

  function parseMap(indent: number): { [k: string]: Y } {
    const out: { [k: string]: Y } = {};
    while (pos < lines.length) {
      const l = lines[pos];
      const ind = indentOf(l.text);
      if (ind < indent) break;
      if (ind > indent) throw new Error(`yaml line ${l.n}: unexpected indent`);
      const t = l.text.trim();
      if (t.startsWith("- ")) break;
      const kv = splitKey(t);
      if (!kv) throw new Error(`yaml line ${l.n}: expected 'key: value'`);
      const [key, val] = kv;
      pos++;
      if (val === "") {
        const next = lines[pos];
        if (next && indentOf(next.text) > indent) out[key] = parseBlock(indentOf(next.text));
        else if (next && indentOf(next.text) === indent && next.text.trimStart().startsWith("- ")) out[key] = parseList(indent);
        else out[key] = null;
      } else out[key] = scalar(val);
    }
    return out;
  }

  const result = parseBlock(0);
  if (pos < lines.length) throw new Error(`yaml line ${lines[pos].n}: trailing content`);
  return result;
}

function stripComment(l: string): string {
  // 따옴표 밖의 ` #` 부터 주석. 줄 시작 `#` 도 주석.
  let q: string | null = null;
  for (let i = 0; i < l.length; i++) {
    const c = l[i];
    if (q) { if (c === q) q = null; continue; }
    if (c === '"' || c === "'") { q = c; continue; }
    if (c === "#" && (i === 0 || /\s/.test(l[i - 1]))) return l.slice(0, i).replace(/\s+$/, "");
  }
  return l.replace(/\s+$/, "");
}

function isMapEntry(s: string): boolean { return splitKey(s.trim()) !== null; }

function splitKey(t: string): [string, string] | null {
  let m = t.match(/^"([^"]*)"\s*:(?:\s+(.*))?$/) ?? t.match(/^'([^']*)'\s*:(?:\s+(.*))?$/);
  if (m) return [m[1], (m[2] ?? "").trim()];
  // 키에 `:` 가 들어갈 수 있다(`qwen3.6-coder:latest:`). 값은 반드시 `: ` 뒤에 온다.
  m = t.match(/^([^\s'"].*?):(?:\s+(.*))?$/);
  if (m) return [m[1], (m[2] ?? "").trim()];
  return null;
}

function scalar(v: string): Y {
  if (v === "" || v === "~" || v === "null") return null;
  if (v === "true") return true;
  if (v === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  let m = v.match(/^"(.*)"$/) ?? v.match(/^'(.*)'$/);
  if (m) return m[1];
  m = v.match(/^\[(.*)\]$/);
  if (m) return m[1].trim() === "" ? [] : m[1].split(",").map((s) => scalar(s.trim()));
  return v;
}

export function get(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}

// --- Modelfile ------------------------------------------------------------------

export type Modelfile = { name: string; from: string | null; params: Record<string, string>; header: string[] };

export function parseModelfile(name: string, text: string): Modelfile {
  const params: Record<string, string> = {};
  let from: string | null = null;
  const header: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const t = line.trim();
    if (t.startsWith("#")) { header.push(t); continue; }
    const pm = t.match(/^PARAMETER\s+(\S+)\s+(.+)$/);
    if (pm) { params[pm[1]] = pm[2].trim(); continue; }
    const fm = t.match(/^FROM\s+(\S+)/);
    if (fm) from = fm[1];
  }
  return { name, from, params, header };
}

// --- 실행 ------------------------------------------------------------------------

/** 독립 실행 진입점. 이슈가 있으면 한 줄씩 stderr 로 내고 exit 1. */
export function runCli(check: Check): void {
  const root = repoRoot();
  let issues: Issue[];
  try { issues = check.run(root); }
  catch (e) { issues = [`${check.name}: 검사 자체가 실패했다 — ${(e as Error).message}`]; }
  for (const n of check.notes?.() ?? []) console.log(`${check.name}: skip — ${n}`);
  if (issues.length === 0) { console.log(`${check.name}: OK`); return; }
  for (const i of issues) console.error(`${check.name}: ${i}`);
  process.exit(1);
}

/** 이 모듈을 직접 실행한 파일인지 (import 됐을 때는 CLI 를 돌리지 않기 위해). */
export function isMain(metaUrl: string): boolean {
  return process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(metaUrl);
}
