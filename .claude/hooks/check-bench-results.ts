/**
 * check-bench-results — bench/ 결과 기록이 bench/README.md 의 표준을 지키는지 검사한다.
 *
 * 규칙: .claude/rules/bench-results.md
 *  - 플랫(하위 디렉터리 없음), 파일명 `<YYYY-MM-DD>.<s1|s2>.<subject>.(md|json)` 또는 README.md
 *  - .json 은 같은 stem 의 .md 가 있거나, 어떤 캠페인 .md 의 출처 절이 그 파일명을 인용해야 한다
 *    (러너 원본 하나가 여러 캠페인의 원본일 수 있다). 유효한 JSON
 *  - .md 는 H1 + 고정 5절(조건/과제/결과/판단/출처) 순서 고정, 결과 절에 필수 열을 가진 표
 *  - 조건 절에 n 표기. n=1 캠페인의 판단은 "잠정"
 *  - README 인덱스: 모든 캠페인 .md 가 링크돼 있고, 링크 대상이 실재한다
 */
import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { type Check, type Issue, isMain, listFiles, read, runCli } from "./lib/harness.ts";

export const FILE_RE = /^(\d{4}-\d{2}-\d{2})\.(s1|s2)\.([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)\.(md|json)$/;
const SECTIONS = ["조건", "과제", "결과", "판단", "출처"];
const RESULT_COLUMNS = ["모델", "과제", "thinking", "소요", "게이트"];

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const dir = "bench";
  if (!existsSync(join(root, dir))) return [`${dir}/ 가 없다`];

  for (const e of readdirSync(join(root, dir))) {
    if (statSync(join(root, dir, e)).isDirectory()) issues.push(`${dir}/${e}/: 하위 디렉터리 금지 — 결과는 플랫하게 둔다`);
  }

  const files = listFiles(root, dir);
  const campaigns = files.filter((f) => f !== "README.md");
  const mds = new Set<string>();
  for (const f of campaigns) {
    const m = f.match(FILE_RE);
    if (!m) { issues.push(`${dir}/${f}: 파일명이 <YYYY-MM-DD>.<s1|s2>.<subject>.(md|json) 이 아니다`); continue; }
    if (m[4] === "md") mds.add(f);
  }
  const cited = new Set<string>();
  for (const f of mds) {
    const src = section(read(root, `${dir}/${f}`) ?? "", "출처") ?? "";
    for (const m of src.matchAll(/`([^`]+\.json)`/g)) cited.add(m[1]);
  }
  for (const f of campaigns) {
    const m = f.match(FILE_RE);
    if (!m) continue;
    if (m[4] === "json") {
      const stem = f.slice(0, -5);
      if (!mds.has(`${stem}.md`) && !cited.has(f)) issues.push(`${dir}/${f}: 같은 stem 의 .md 도, 출처 절에서 이 파일을 인용한 .md 도 없다`);
      try { JSON.parse(read(root, `${dir}/${f}`) ?? ""); } catch (e) { issues.push(`${dir}/${f}: JSON 파싱 실패 — ${(e as Error).message}`); }
    } else {
      issues.push(...checkCampaignMd(`${dir}/${f}`, read(root, `${dir}/${f}`) ?? ""));
    }
  }

  const readme = read(root, `${dir}/README.md`);
  if (readme === null) { issues.push(`${dir}/README.md 가 없다`); return issues; }
  const idx = section(readme, "인덱스");
  if (idx === null) issues.push(`${dir}/README.md: "## 인덱스" 절이 없다`);
  else {
    const linked = new Set([...idx.matchAll(/\]\(([^)]+\.md)\)/g)].map((m) => m[1]));
    for (const f of mds) if (!linked.has(f)) issues.push(`${dir}/README.md 인덱스에 ${f} 가 없다`);
    for (const l of linked) if (!existsSync(join(root, dir, l))) issues.push(`${dir}/README.md 인덱스가 없는 파일을 가리킨다: ${l}`);
  }
  for (const s of ["표준", "인덱스", "종합"]) if (section(readme, s) === null) issues.push(`${dir}/README.md: "## ${s}" 절이 없다`);
  return issues;
}

function checkCampaignMd(rel: string, text: string): Issue[] {
  const issues: Issue[] = [];
  if (!/^# .+/m.test(text.split("\n")[0] ?? "")) issues.push(`${rel}: 첫 줄이 H1 제목이 아니다`);
  const heads = [...text.matchAll(/^## (\S+)(.*)$/gm)].map((m) => m[1]);
  if (heads.join("|") !== SECTIONS.join("|")) {
    issues.push(`${rel}: 절이 [${SECTIONS.join(", ")}] 순서·제목과 다르다 — 실제 [${heads.join(", ")}]`);
    return issues;
  }
  const cond = section(text, "조건") ?? "";
  const nMatch = cond.match(/n\s*[=≥>]\s*(\d+)/);
  if (!nMatch) issues.push(`${rel}: 조건 절에 n 표기(n=1, n≥2 …)가 없다`);
  const res = section(text, "결과") ?? "";
  const header = res.split("\n").find((l) => l.trim().startsWith("|"));
  if (!header) issues.push(`${rel}: 결과 절에 표가 없다`);
  else {
    const cols = header.split("|").map((c) => c.trim().toLowerCase());
    for (const c of RESULT_COLUMNS) {
      if (!cols.some((x) => x.includes(c.toLowerCase()))) issues.push(`${rel}: 결과 표에 "${c}" 열이 없다`);
    }
  }
  const judge = text.match(/^## 판단.*$/m)?.[0] ?? "";
  const judgeBody = section(text, "판단") ?? "";
  if (nMatch && nMatch[1] === "1" && !/잠정/.test(judge + judgeBody)) issues.push(`${rel}: n=1 인데 판단에 "잠정" 표기가 없다`);
  const src = section(text, "출처") ?? "";
  if (src.trim() === "") issues.push(`${rel}: 출처 절이 비어 있다`);
  return issues;
}

/** `## <title>` 로 시작하는 절의 본문(다음 `## ` 전까지). 없으면 null. */
export function section(text: string, title: string): string | null {
  const re = new RegExp(`^## ${title}(?:[ \\t].*)?$`, "m");
  const m = text.match(re);
  if (!m || m.index === undefined) return null;
  const rest = text.slice(m.index + m[0].length);
  const next = rest.search(/^## /m);
  return next === -1 ? rest : rest.slice(0, next);
}

export const check: Check = { name: "check-bench-results", run };
if (isMain(import.meta.url)) runCli(check);
