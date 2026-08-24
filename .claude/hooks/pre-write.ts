/**
 * pre-write — PreToolUse(Edit|Write). 레이아웃 규칙을 파일이 생기기 전에 막는다.
 *
 *  - bench/: 플랫. README.md 또는 `<YYYY-MM-DD>.<s1|s2>.<subject>.(md|json)` 만. 하위 디렉터리 금지
 *    (bench/README.md "표준", 수행 환경은 .claude/skills/llm-bench/ 와 sandbox/ 에 둔다)
 *  - .claude/hooks/**: .ts 만. .claude/rules/: .md 만
 *  - sandbox/.omp/**: 피험자 하네스 — 벤치 결과를 오염시키므로 편집 금지(사용자 명시 요청 시 규칙 파일을 먼저 고친다)
 */
import { deny, guarded, readHookInput } from "./lib/hook-io.ts";
import { repoRoot, toRel } from "./lib/harness.ts";
import { FILE_RE } from "./check-bench-results.ts";

guarded("pre-write", () => {
  const input = readHookInput();
  const abs = input.tool_input?.file_path;
  if (!abs) return;
  const rel = toRel(repoRoot(), abs);
  if (rel.startsWith("..")) return;

  const bench = rel.match(/^bench\/(.+)$/);
  if (bench) {
    const name = bench[1];
    if (name.includes("/")) deny("PreToolUse", `bench/ 는 플랫이다 — 하위 디렉터리 금지(${rel}). 결과는 bench/<date>.<s1|s2>.<subject>.md 로, 수행 환경은 .claude/skills/llm-bench/ 로.`);
    if (name !== "README.md" && !FILE_RE.test(name)) deny("PreToolUse", `bench/${name}: 파일명은 <YYYY-MM-DD>.<s1|s2>.<subject>.(md|json) (subject 는 소문자·숫자·점·하이픈). bench/README.md "표준" 참고.`);
  }
  if (/^\.claude\/hooks\/.+/.test(rel) && !rel.endsWith(".ts")) deny("PreToolUse", `${rel}: .claude/hooks/ 는 TypeScript 만 쓴다(도구 언어 하나, node 로 직접 실행).`);
  if (/^\.claude\/rules\/.+/.test(rel) && !rel.endsWith(".md")) deny("PreToolUse", `${rel}: .claude/rules/ 는 .md 규칙 파일만 둔다.`);
  if (/^sandbox\/\.omp\//.test(rel)) deny("PreToolUse", `${rel}: sandbox/.omp 는 2단계 벤치 피험자의 하네스다 — 편집하면 캠페인 간 비교가 깨진다. 사용자가 명시적으로 요청한 경우에만 고친다.`);
});
