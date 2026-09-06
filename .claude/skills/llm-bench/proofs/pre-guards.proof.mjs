// pre/ 가드 경계 프루프 — 파일 배치(strict-tooling.ts), 백엔드 구조(strict-backend-app-structure.ts),
// 명령 라우팅(strict-command-routing.ts), 서브에이전트 금지(strict-no-subagents.ts).
// 가드마다 프루프가 하나는 이름을 불러야 한다(`make check-harness-proofs`) — 초록 프루프는
// "이 가드가 옳다"가 아니라 "프루프가 태운 모양에서 옳다"는 뜻이라, 이름조차 안 불린 가드는
// 아무 경계도 고정돼 있지 않다.
// 경로는 이식성을 위해 import.meta.url 로 풀고, 픽스처는 os.tmpdir() 아래에만 만든다.
import { tmpdir } from "node:os";
import { mkdirSync, rmSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const FIX = join(tmpdir(), "llm-bench-proof-fixtures", "pre-guards");
rmSync(FIX, { recursive: true, force: true });
mkdirSync(FIX, { recursive: true });
process.chdir(FIX); // 가드들은 import 시점에 process.cwd() 로 프로젝트 루트를 잡는다

let bad = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) bad++; };
const blocked = (r) => !!r && r.block === true;

async function load(file) {
  let handler;
  const mod = await import(pathToFileURL(join(REPO, "sandbox/.omp/hooks/pre", file)).href);
  mod.default({ on: (_event, fn) => { handler = fn; } });
  return (toolName, input) => handler({ toolName, input }, {});
}

// --- strict-tooling.ts — 파일이 어디에 생기는가(write 전용) ---
const tooling = await load("strict-tooling.ts");
check("T1 루트 밖 파이썬 스크립트 write BLOCK",
  blocked(tooling("write", { path: "utils/helper.py" })));
check("T2 애플리케이션 코드 write 통과",
  !blocked(tooling("write", { path: "backend/app/services/notice.py" })));
// 2c: 이미 잘못된 자리에 있는 파일을 고치는 편집은 앞으로 나아가는 작업이다 — 막으면 파일은
// 그 자리에 남고 사후 검사가 잔소리만 하는 상태가 된다.
check("T3 잘못 놓인 파일의 edit 은 통과(fix-forward)",
  !blocked(tooling("edit", { path: "utils/helper.py" })));
check("T4 .omp/hooks 아래 비-TypeScript write BLOCK",
  blocked(tooling("write", { path: ".omp/hooks/post/check-x.js" })));
check("T5 두 번째 셸 스크립트 write BLOCK",
  blocked(tooling("write", { path: "scripts/run.sh" })));
check("T6 중복 경로는 어느 도구로 와도 그 사실을 먼저 말한다",
  /두 번/.test(tooling("edit", { path: "backend/backend/app/main.py" })?.reason ?? ""));
check("T7 frontend 스크립트 write 통과",
  !blocked(tooling("write", { path: "frontend/src/app.ts" })));
check("T8 내용 태그가 붙은 경로도 확장자 판정이 살아 있다",
  blocked(tooling("write", { path: "utils/helper.py#0D77" })));
check("T9 셸은 이 가드의 대상이 아니다",
  !blocked(tooling("bash", { command: "touch utils/helper.py" })));

// --- strict-backend-app-structure.ts — 문서화된 backend/ 구조 밖 생성 금지 ---
const structure = await load("strict-backend-app-structure.ts");
check("S1 app/ 아래 새 디렉터리 BLOCK",
  blocked(structure("write", { path: "backend/app/adapters/client.py" })));
check("S2 앵커드 편집(내용 태그)은 허용 파일을 허용으로 읽는다",
  !blocked(structure("edit", { path: "backend/app/main.py#0D77" })));
check("S3 app 루트의 낯선 파일 BLOCK",
  blocked(structure("write", { path: "backend/app/stray.py" })));
check("S4 backend/ 아래 비표준 디렉터리 BLOCK",
  blocked(structure("write", { path: "backend/workers/runner.py" })));
check("S5 표준 디렉터리 통과",
  !blocked(structure("write", { path: "backend/app/models/notice.py" })));
check("S6 tests 통과",
  !blocked(structure("write", { path: "backend/tests/test_notice.py" })));

// --- strict-frontend-app-structure.ts — 선언된 frontend/src/ 레이아웃(SRC_LAYOUT) 밖 생성 금지 ---
// 백엔드 쌍둥이(2026-09-06 fas 이식). 재귀 스캔은 낯선 디렉터리를 보긴 하지만 디렉터리 역할에
// 걸린 규칙(sections=화면·lib/api=전송)이 조용히 적용되지 않는다 — 그래서 write 시점에 막는다.
const fstructure = await load("strict-frontend-app-structure.ts");
check("F1 src/ 아래 새 디렉터리 BLOCK",
  blocked(fstructure("write", { path: "frontend/src/adapters/client.ts" })));
check("F2 선언된 디렉터리(sections) 통과",
  !blocked(fstructure("write", { path: "frontend/src/sections/notice/NoticeList.tsx" })));
check("F3 src 루트의 낯선 파일 BLOCK",
  blocked(fstructure("write", { path: "frontend/src/stray.ts" })));
check("F4 src 루트의 선언된 파일(App.tsx) 통과",
  !blocked(fstructure("edit", { path: "frontend/src/App.tsx" })));
check("F5 내용 태그가 붙은 허용 경로도 허용으로 읽는다",
  !blocked(fstructure("write", { path: "frontend/src/types/notice.ts#0D77" })));
check("F6 src/ 밖(frontend 설정 파일)은 이 가드의 대상이 아니다",
  !blocked(fstructure("write", { path: "frontend/vite.config.ts" })));
check("F7 플러그인 편집 툴(replace)의 평문 path 도 같은 경계",
  blocked(fstructure("replace", { path: "frontend/src/adapters/client.ts" })));

// --- strict-command-routing.ts — make 타깃으로 라우팅 ---
const routing = await load("strict-command-routing.ts");
check("R1 bare pytest BLOCK", blocked(routing("bash", { command: "pytest -q" })));
check("R2 make 는 통과", !blocked(routing("bash", { command: "make test" })));
check("R3 eval 본문의 subprocess 실행도 같은 우회다",
  blocked(routing("eval", { code: 'subprocess.run(["pytest", "-q"], check=True)' })));
check("R4 도구를 부르지 않는 eval 본문은 통과",
  !blocked(routing("eval", { code: "print(sum(range(10)))" })));
check("R5 인자로 쓰인 바이너리 경로는 호출이 아니다",
  !blocked(routing("bash", { command: "ls backend/.venv/bin/ruff" })));
check("R6 안내문이 권하는 절대경로 파이썬은 스스로 막지 않는다",
  !blocked(routing("bash", { command: 'backend/.venv/bin/python -c "print(1)"' })));
check("R7 docker compose 직접 실행 BLOCK",
  blocked(routing("bash", { command: "docker compose up -d" })));

// --- strict-no-subagents.ts — 도구 이름만 보고 무조건 막는다 ---
const subagents = await load("strict-no-subagents.ts");
check("A1 task 도구 BLOCK", blocked(subagents("task", { prompt: "do it" })));
check("A2 agent 종류를 붙여도 BLOCK(허용 목록은 우회 가능해서 없다)",
  blocked(subagents("task", { agent: "general-purpose", prompt: "do it" })));
check("A3 다른 도구는 통과", !blocked(subagents("bash", { command: "make verify" })));

console.log(bad ? `\n${bad} FAILED` : "\nall green");
process.exit(bad ? 1 : 0);
