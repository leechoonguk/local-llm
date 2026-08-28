// 훅 경로 게이트 프루프 — 훅은 자기 도메인 이벤트에만 돈다.
// 근거(2026-08-29 실측): 변이 도구 결과 1회당 post 훅 36개가 write 6.8초 / bash 4.9초를 썼고,
// 그중 3.3초가 backend 편집과 무관한 하네스 메타 검사였다.
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const { touchesPath, touchesStrict } = await import(pathToFileURL(REPO + "/sandbox/.omp/hooks/lib/hook-scope.ts").href);

let failures = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) failures++; };
const ev = (toolName, input) => ({ toolName, input });

check("S1: backend write matches a backend scope",
  touchesPath(ev("write", { path: "backend/app/models/notice.py" }), ["backend/"]));
check("S2: backend write does not match the .omp scope",
  !touchesStrict(ev("write", { path: "backend/app/models/notice.py" }), [".omp/"]));
check("S3: harness edit matches the .omp scope",
  touchesStrict(ev("edit", { path: ".omp/hooks/post/check-backend-naming.ts" }), [".omp/"]));
check("S4: absolute paths match too",
  touchesPath(ev("edit", { path: "/Users/x/repo/sandbox/backend/app/main.py" }), ["backend/"]));
check("S5: shell passes the path-only gate (a command may create files anywhere)",
  touchesPath(ev("bash", { command: "make db-migrate" }), ["backend/"]));
check("S6: shell is filtered by the strict gate when the domain is absent",
  !touchesStrict(ev("bash", { command: "ls backend/app" }), [".omp/"]));
check("S7: shell passes the strict gate when the domain appears",
  touchesStrict(ev("bash", { command: "cat .omp/rules/omp-hooks.md" }), [".omp/"]));
check("S8: an event with no path and no command is never skipped",
  touchesPath(ev("task", {}), ["backend/"]) && touchesStrict(ev("task", {}), [".omp/"]));
check("S9: eval code is read by the strict gate",
  touchesStrict(ev("eval", { code: "require('.omp/hooks/lib/x.ts')" }), [".omp/"]));
check("S10: multiple prefixes — any match is enough",
  touchesPath(ev("write", { path: "frontend/src/App.tsx" }), ["backend/", "frontend/"]));

console.log(failures ? `\n${failures} FAILED` : "\nall green");
process.exit(failures ? 1 : 0);
