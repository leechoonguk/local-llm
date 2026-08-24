/**
 * check-skills — .claude/skills/<name>/SKILL.md 의 프런트매터와 CLAUDE.md 등재.
 *
 * 규칙: .claude/rules/skills.md
 *  - 디렉터리마다 SKILL.md. 프런트매터 name == 디렉터리명, description 은 비어 있지 않고 1536자 이하
 *    (공식: description + when_to_use 합산 1536자에서 잘린다)
 *  - CLAUDE.md "## 디렉터리" 절이 스킬 이름을 적는다
 */
import { existsSync } from "node:fs";
import { join } from "node:path";
import { type Check, type Issue, isMain, listDirs, parseFrontmatter, read, runCli } from "./lib/harness.ts";
import { section } from "./check-bench-results.ts";

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const dirs = listDirs(root, ".claude/skills");
  if (dirs.length === 0) issues.push(".claude/skills/ 에 스킬이 없다");
  const claudeDir = section(read(root, "CLAUDE.md") ?? "", "디렉터리") ?? "";
  for (const d of dirs) {
    const rel = `.claude/skills/${d}/SKILL.md`;
    if (!existsSync(join(root, rel))) { issues.push(`${rel} 가 없다`); continue; }
    const fm = parseFrontmatter(read(root, rel) ?? "");
    if (!fm) { issues.push(`${rel}: 프런트매터가 없다`); continue; }
    if (fm.data.name !== d) issues.push(`${rel}: name(${String(fm.data.name)}) 이 디렉터리명과 다르다`);
    const desc = fm.data.description;
    if (typeof desc !== "string" || desc.trim() === "") issues.push(`${rel}: description 이 없다`);
    else {
      const total = desc.length + (typeof fm.data.when_to_use === "string" ? fm.data.when_to_use.length : 0);
      if (total > 1536) issues.push(`${rel}: description(+when_to_use) ${total}자 > 1536`);
    }
    if (!claudeDir.includes(d)) issues.push(`CLAUDE.md "## 디렉터리" 절에 스킬 ${d} 가 없다`);
  }
  return issues;
}

export const check: Check = { name: "check-skills", run };
if (isMain(import.meta.url)) runCli(check);
