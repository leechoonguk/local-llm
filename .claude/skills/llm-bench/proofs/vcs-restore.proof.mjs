// 벤치 셀에서 VCS 복원 차단 프루프.
// 근거(2026-08-29, harnessv2 integration 셀): 피험자가 Mode A 로 지워진 참조 구현을
// `git checkout HEAD -- …` 로 되살리고 "make verify 통과"로 종료했다 — 1248초·writes 2·산출물 0/6.
// 게이트는 초록이었지만 측정된 것은 없다. 인터랙티브에서는 정당하므로 셀 모드에서만 막는다.
import { resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const mod = await import(pathToFileURL(REPO + "/sandbox/.omp/hooks/pre/strict-no-vcs-publish.ts").href);

let failures = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) failures++; };
const run = (command) => { let h; mod.default({ on: (_e, f) => { h = f; } }); return h({ toolName: "bash", input: { command } }, {}); };
const blocked = (r) => !!r && r.block === true;

process.env.BENCH_CELL = "1";
check("R1: a cell cannot restore deleted artifacts from HEAD",
  blocked(run("git checkout HEAD -- api/integration.search-barcode-item-info.http")));
check("R2: git restore is the same move", blocked(run("git restore --source=HEAD backend/app/models/notice.py")));
check("R3: so is reset --hard", blocked(run("git reset --hard HEAD")));
check("R4: so is stash pop", blocked(run("git stash pop")));
// 범위 축소(2026-08-30 전수 점검): `--oneline` 로그는 내용을 되살리지 않는다. 22건 중 18건이 즉시
// 재시도였고, 그중엔 "이 리비전은 푸시됐나"에 답하려던 호출이 있었다 — 그 질문은 우리 규칙이 만든다.
check("R5: a plain log listing is allowed in a cell", !blocked(run("git log --oneline -5")));
check("R5b: but `git log -p` recovers content and is blocked", blocked(run("git log -p -- backend/app")));
check("R5c: ls-files / merge-base answer 'is it pushed' and pass",
  !blocked(run("git ls-files --error-unmatch backend/app/main.py")) && !blocked(run("git merge-base --is-ancestor HEAD origin/main")));
check("R6: diffing still blocked (it prints content)", blocked(run("git diff -- backend/app")));
check("R7: commit/push stay blocked in a cell too", blocked(run("git commit -m x")));
check("R8: the reason points at implementing, not recovering", /직접 만들어야/.test(run("git checkout HEAD -- x.py")?.reason ?? ""));
check("R11: a cell cannot read the answer out of history either",
  blocked(run("git show HEAD:sandbox/api/integration.search-barcode-item-info.http")));
check("R12: quoted execSync in an eval body is the same read path", blocked(run("execSync('git show HEAD:x.py')")));
check("R13: git diff HEAD too", blocked(run("git diff HEAD -- sandbox/backend")));
delete process.env.BENCH_CELL;
check("R9: interactive sessions may restore and read freely",
  !blocked(run("git checkout HEAD -- backend/app/models/notice.py")) && !blocked(run("git show HEAD:x.py")));
check("R10: interactive commit/push still blocked (user-only)", blocked(run("git push origin main")));

console.log(failures ? `\n${failures} FAILED` : "\nall green");
process.exit(failures ? 1 : 0);
