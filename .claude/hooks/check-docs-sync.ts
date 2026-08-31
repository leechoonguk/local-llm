/**
 * check-docs-sync — CLAUDE.md / README.md 가 설정 파일과 어긋나지 않는지.
 *
 * 규칙: .claude/rules/docs-sync.md
 *  - CLAUDE.md "기본 코더: `X`" == omp/config.fragment.yml modelRoles.default, "보조: `Y`" == modelRoles.tiny
 *  - CLAUDE.md 가 README "제목" 으로 인용하는 절은 README.md 에 실재한다
 *  - README "## 파일" 블록은 ollama/, omlx/, omp/ 의 모든 파일과 하네스 경로(Makefile, .claude/rules/, .claude/hooks/)를 적는다
 *  - README 는 `make verify` 를 언급한다(검증 진입점이 문서에 있어야 한다)
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { type Check, type Issue, isMain, listFiles, parseYaml, read, runCli } from "./lib/harness.ts";
import { section } from "./check-bench-results.ts";

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const claude = read(root, "CLAUDE.md"), readme = read(root, "README.md"), frag = read(root, "omp/config.fragment.yml");
  if (claude === null) return ["CLAUDE.md 가 없다"];
  if (readme === null) return ["README.md 가 없다"];

  if (frag !== null) {
    try {
      const roles = ((parseYaml(frag) as Record<string, unknown>).modelRoles ?? {}) as Record<string, unknown>;
      const pairs: Array<[string, string]> = [["기본 코더", "default"], ["보조", "tiny"]];
      for (const [label, role] of pairs) {
        const m = claude.match(new RegExp(`${label}: \`([^\`]+)\``));
        if (!m) issues.push(`CLAUDE.md: "${label}: \`…\`" 표기가 없다`);
        else if (roles[role] !== undefined && m[1] !== roles[role]) issues.push(`CLAUDE.md ${label} \`${m[1]}\` != config.fragment.yml modelRoles.${role} \`${String(roles[role])}\``);
      }
    } catch { /* omp-models 가 파싱 오류를 보고한다 */ }
  }

  const headings = [...readme.matchAll(/^#{2,4} (.+)$/gm)].map((m) => m[1]);
  for (const m of claude.matchAll(/README(?:\.md)? "([^"]+)"/g)) {
    if (!headings.some((h) => h.includes(m[1]))) issues.push(`CLAUDE.md 가 README "${m[1]}" 을 인용하지만 그런 제목의 절이 없다`);
  }

  const files = section(readme, "파일");
  if (files === null) issues.push('README.md: "## 파일" 절이 없다');
  else {
    for (const dir of ["ollama", "omlx", "omp"]) for (const f of listFiles(root, dir)) {
      if (!files.includes(f)) issues.push(`README.md "파일" 절에 ${dir}/${f} 가 없다`);
    }
    for (const p of ["Makefile", ".claude/", "rules/", "hooks/"]) if (!files.includes(p)) issues.push(`README.md "파일" 절에 ${p} 가 없다`);
  }
  if (!readme.includes("make verify")) issues.push("README.md 가 `make verify` 를 언급하지 않는다");
  issues.push(...checkOmlxIdReferences(root));
  return issues;
}


/**
 * 스킬·CLAUDE.md 의 `omlx/<id>` 참조는 서빙 실체여야 한다 (2026-09-01).
 * 실측 부류 "유령 모델 id": 프로파일 suffix 폐지(08-31) 뒤에도 bake-config 표가
 * `…:coder` 를, llm-bench 가 옛 롱 id 를 부르고 있었다. 권위는 omlx/model_settings.json
 * 의 비숨김 항목이다(README 는 실측 기록이 섞여 있어 제외 — 역사 표의 옛 id 는 정당하다).
 */
function checkOmlxIdReferences(root: string): Issue[] {
  const issues: Issue[] = [];
  const settings = ((): Record<string, { is_hidden?: boolean }> => {
    try { return (JSON.parse(readFileSync(join(root, "omlx", "model_settings.json"), "utf-8")) as { models: Record<string, { is_hidden?: boolean }> }).models; }
    catch { return {}; }
  })();
  const serving = new Set(Object.entries(settings).filter(([, v]) => v.is_hidden !== true).map(([k]) => k));
  if (serving.size === 0) return issues;
  const files = [join(root, "CLAUDE.md")];
  const skills = join(root, ".claude", "skills");
  if (existsSync(skills)) for (const d of readdirSync(skills)) {
    const f = join(skills, d, "SKILL.md");
    if (existsSync(f)) files.push(f);
  }
  for (const file of files) {
    const text = readFileSync(file, "utf-8");
    text.split("\n").forEach((line, i) => {
      if (/제거|폐지|기각|였다|옛|과거|history/.test(line)) return; // 역사 서술은 옛 id 가 정당하다
      for (const m of line.matchAll(/omlx\/([A-Za-z][\w.:-]*\d[\w.:-]*)/g)) {
        const id = m[1].replace(/[.,)`'"]+$/, "");
        if (!serving.has(id)) {
          issues.push(`${file.replace(root + "/", "")}:${i + 1}: omlx/${id} — 서빙 항목이 아니다(model_settings 비숨김 기준). 유령 id 를 고치거나 역사 서술로 표시하라`);
        }
      }
    });
  }
  return issues;
}

export const check: Check = { name: "check-docs-sync", run };
if (isMain(import.meta.url)) runCli(check);
