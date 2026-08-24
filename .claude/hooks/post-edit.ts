/**
 * post-edit — PostToolUse(Edit|Write) 디스패처.
 *
 *  1. 편집된 파일 경로를 `.claude/rules/<name>.md` 의 `paths` 와 대조해 해당 검사(check-<name>)만 실행한다.
 *     (검사 선택 기준이 규칙 파일 자체다 — 규칙의 paths 가 곧 훅의 트리거. Claude Code 가 규칙 본문을
 *     경로 조건으로 로드하는 것과 같은 기준.)
 *  2. 위반이 있으면 exit 2 + stderr (모델에 전달). 파일당 최대 8줄, 나머지는 `make check-<name>` 으로 안내.
 *  3. 위반이 없고 라이브 반영이 필요한 파일이면 additionalContext 로 알린다(omp/ → ~/.omp/agent, Modelfile → ollama create,
 *     omlx/ → ~/.omlx + 서버 재시작). 자동 복사는 하지 않는다 — config.yml 은 omp 자신의 상태가 섞여 있다.
 */
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { addContext, block, guarded, readHookInput } from "./lib/hook-io.ts";
import { type Check, listFiles, matchesAny, parseFrontmatter, read, repoRoot, toRel } from "./lib/harness.ts";

const MAX_LINES = 8;

guarded("post-edit", async () => {
  const input = readHookInput();
  const abs = input.tool_input?.file_path;
  if (!abs) return;
  const root = repoRoot();
  const rel = toRel(root, abs);
  if (rel.startsWith("..")) return;

  const selected: string[] = [];
  for (const f of listFiles(root, ".claude/rules")) {
    if (!f.endsWith(".md")) continue;
    const fm = parseFrontmatter(read(root, `.claude/rules/${f}`) ?? "");
    const paths = fm?.data.paths;
    if (Array.isArray(paths) && matchesAny(rel, paths as string[])) selected.push(f.slice(0, -3));
  }

  const lines: string[] = [];
  for (const name of selected) {
    const file = join(root, ".claude/hooks", `check-${name}.ts`);
    let issues: string[];
    try {
      const mod = (await import(pathToFileURL(file).href)) as { check: Check };
      issues = mod.check.run(root);
    } catch (e) { issues = [`검사 자체가 실패했다 — ${(e as Error).message}`]; }
    if (issues.length === 0) continue;
    lines.push(`[check-${name}] ${rel} 편집 후 위반 ${issues.length}건 (규칙: .claude/rules/${name}.md)`);
    for (const i of issues.slice(0, MAX_LINES)) lines.push(`  - ${i}`);
    if (issues.length > MAX_LINES) lines.push(`  … ${issues.length - MAX_LINES}건 더: make check-${name}`);
  }
  if (lines.length) block(lines);

  const reminder = liveSyncReminder(rel);
  if (reminder) addContext("PostToolUse", reminder);
});

function liveSyncReminder(rel: string): string | null {
  if (/^omp\/(models\.yml|config\.fragment\.yml)$/.test(rel)) return "omp 설정이 바뀌었다. 라이브(`omp config path`, 기본 ~/.omp/agent)에 반영할 것: models.yml 은 cp, config.yml 은 modelRoles 만 손으로. 끝나면 /v1 nothink 스모크 테스트.";
  const mf = rel.match(/^ollama\/Modelfile\.(.+)$/);
  if (mf) return `Modelfile 이 바뀌었다. 'ollama create ${mf[1]} -f ${rel}' 로 다시 만들어야 반영된다.`;
  if (/^omlx\/model_(settings|profiles)\.json$/.test(rel)) return `${rel} 이 바뀌었다. ~/.omlx/ 로 복사하고 'omlx restart'(메뉴바 앱) 후 admin 로그의 total: 로 단일 상주를 확인할 것.`;
  return null;
}
