import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/**
 * Strict-Tooling Pre Hook
 *
 * Enforces the tooling language policy (tooling.md) at write time:
 *
 *   - Python is application code only — `backend/app`, `backend/tests`,
 *     `backend/alembic`. A Python script anywhere else is automation, and
 *     automation belongs in `.omp/hooks/` as TypeScript, runnable by a make
 *     target on every machine that has node.
 *   - Shell is limited to `backend/scripts/start.sh`, the app's entrypoint.
 *     A second shell script is an unreviewable, untestable check.
 *   - `.omp/hooks/` holds TypeScript only, so every hook and lib is read,
 *     imported and type-checked the same way.
 *   - Ad-hoc script directories (`scripts/`, `tools/`, `bin/` at the root) are
 *     blocked: tooling that is not under `.omp/hooks/` is not discovered by
 *     `check-omp-hooks`, not registered in a Makefile, and not run by CI.
 *
 * To add/remove locations: edit the allowlists below. No other logic changes.
 */
const PYTHON_ROOTS = ["backend/app/", "backend/tests/", "backend/alembic/"];
const SHELL_FILES: Record<string, true> = { "backend/scripts/start.sh": true };
const SCRIPT_ROOTS = [".omp/hooks/", ".omp/extensions/", "frontend/", "decks/"];
const ADHOC_SCRIPT_DIRS = /^(?:scripts|tools|bin|utils)\//;

const projectRoot = `${process.cwd()}/`;

export default function strictTooling(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    // 중복 경로 오타를 먼저 짚는다. 전수 점검(2026-08-30): `.py` 차단 9건 중 6건이
    // `backend/backend/app/...`·`sandbox/sandbox/...` 였는데, 안내는 "파이썬 스크립트 금지 — TypeScript 로
    // 옮기라"였다. 모델은 FastAPI 서비스를 TypeScript 로 다시 쓰라는 말로 읽고 같은 경로를 재시도했다.
    {
      const p0 = String((event.input as any)?.path ?? "").replace(/#[0-9A-Fa-f]{4}$/, "");
      const dup = /(^|\/)(backend|sandbox|frontend)\/\2\//.exec(p0);
      if (dup) {
        return {
          block: true,
          reason: `\`${p0}\` — 경로에 \`${dup[2]}\` 가 두 번 들어갔다. 저장소 루트 기준 경로로 다시 쓰세요.`,
        };
      }
    }
    if (event.toolName !== "write" && event.toolName !== "edit") return;

    const path = normalize(String((event.input as Record<string, unknown>)?.path ?? ""));
    if (path === "") return;

    if (path.endsWith(".py") && !PYTHON_ROOTS.some((root) => path.startsWith(root))) {
      return {
        block: true,
        reason:
          `\`${path}\` — 파이썬 스크립트 금지 (tooling.md)\n\n` +
          "파이썬은 애플리케이션 코드 전용입니다:\n" +
          "  backend/app, backend/tests, backend/alembic\n\n" +
          "스크립트성 코드는 TypeScript로 훅 하위에 두세요:\n" +
          "  .omp/hooks/post/check-<name>.ts  (자동 검사)\n" +
          "  .omp/hooks/lib/<scope>-<name>.ts (러너/공유 로직, make 타겟으로 실행)",
      };
    }

    if (path.endsWith(".sh") && SHELL_FILES[path] !== true) {
      return {
        block: true,
        reason:
          `\`${path}\` — 셸 스크립트 추가 금지 (tooling.md)\n\n` +
          "허용된 셸 스크립트는 backend/scripts/start.sh 하나입니다.\n" +
          "검사·러너는 .omp/hooks/ 하위 TypeScript로 작성하고 make 타겟에 등록하세요.",
      };
    }

    if (/^\.omp\/(hooks|extensions)\//.test(path) && /\.(js|jsx|mjs|cjs|py|sh)$/.test(path)) {
      return {
        block: true,
        reason:
          `\`${path}\` — .omp/hooks/ 와 .omp/extensions/ 는 TypeScript만 허용 (tooling.md)\n\n` +
          "확장자를 .ts 로 두세요 — node가 타입을 스트립해 그대로 실행합니다.",
      };
    }

    if (ADHOC_SCRIPT_DIRS.test(path)) {
      return {
        block: true,
        reason:
          `\`${path}\` — 저장소 루트 스크립트 디렉토리 금지 (tooling.md)\n\n` +
          "검사·러너는 .omp/hooks/ 하위에, 실행은 make 타겟으로:\n" +
          "  .omp/hooks/lib/<scope>-<name>.ts + Makefile 타겟",
      };
    }

    if (/\.(ts|tsx|mjs|cjs)$/.test(path) && !SCRIPT_ROOTS.some((root) => path.startsWith(root))) {
      return {
        block: true,
        reason:
          `\`${path}\` — 인정되지 않은 위치의 스크립트 (tooling.md)\n\n` +
          "허용 위치: .omp/hooks/, .omp/extensions/, frontend/, decks/",
      };
    }
  });
}

/** An absolute or `./`-prefixed path is the same file as the repo-relative one. */
function normalize(path: string): string {
  const relative = path.startsWith(projectRoot) ? path.slice(projectRoot.length) : path;
  return relative.replace(/^\.\//, "");
}
