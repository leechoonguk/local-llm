// Unit proof for strict-additive-writes (synthetic tool_call events, no GPU).
// 1-5: the original five cases (import swap / add alongside / shrinking delete /
//      rename sweep / pure import removal). 6-8: the new unwrap rule.
// 이 파일은 세션 스크래치가 아니라 레포 자산이다(2026-08-28 이관) — `make check-harness-proofs`.
// 경로는 이식성을 위해 import.meta.url 과 os.tmpdir() 로 푼다.
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const FIXROOT = join(tmpdir(), "llm-bench-proof-fixtures");
const hook = (await import(pathToFileURL(REPO + "/sandbox/.omp/hooks/pre/strict-additive-writes.ts").href)).default;

const handlers = {};
hook({ on: (e, h) => { handlers[e] = h; } });
const edit = (old_string, new_string) => handlers.tool_call({ toolName: "edit", input: { path: "backend/app/services/batch.py", old_string, new_string } }, {});

let bad = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) bad++; };

// 1. import swap -> BLOCK
check("1 import swap BLOCK", edit("from app.models.user import User", "from app.models.notice import Notice")?.block === true);
// 2. import added alongside -> pass
check("2 add alongside pass", edit("from app.models.user import User", "from app.models.user import User\nfrom app.models.notice import Notice") === undefined);
// 3. shrinking bulk delete (10 -> 1 lines) -> BLOCK
check("3 shrink delete BLOCK", edit(Array.from({length:10},(_,i)=>`line_${i} = compute_${i}()`).join("\n"), "line_0 = compute_0()")?.block === true);
// 4. same-size wholesale modification (rename sweep) -> pass
check("4 rename sweep pass", edit(Array.from({length:10},(_,i)=>`old_${i} = calc_${i}()`).join("\n"), Array.from({length:10},(_,i)=>`new_${i} = calc_${i}()`).join("\n")) === undefined);
// 5. pure import removal (no new import) -> pass
check("5 pure removal pass", edit("import unused_module\nx = 1", "x = 1") === undefined);

// 6. unwrap: context manager line removed, body survives -> BLOCK (measured v2 cell #2 class)
const wrapped = "async def create(self, data):\n    async with self.session.begin():\n        obj = Batch(**data)\n        self.session.add(obj)\n        return obj";
const unwrapped = "async def create(self, data):\n    obj = Batch(**data)\n    self.session.add(obj)\n    return obj";
check("6 unwrap BLOCK", edit(wrapped, unwrapped)?.block === true);
// 7. adding a wrapper around existing code -> pass
check("7 wrap-add pass", edit(unwrapped, wrapped) === undefined);
// 8. replacing wrapper AND body together (nothing survives) -> not the unwrap class -> pass
check("8 full replace pass", edit("with lock:\n    do_old()", "run_new_thing()") === undefined);

// 9-13: omp 18 patch-form cases (measured grammar: PUT N.: replace / PUT N+k@: insert)
const { mkdirSync, writeFileSync, rmSync } = await import("node:fs");
const FIX = join(FIXROOT, "addfix");
rmSync(FIX, { recursive: true, force: true });
mkdirSync(FIX + "/backend/app/dependencies", { recursive: true });
mkdirSync(FIX + "/backend/app/services", { recursive: true });
writeFileSync(FIX + "/backend/app/dependencies/services.py",
  "from app.services.user import UserService\nx = 1\nUserServiceDep = Annotated[UserService, Depends(get_user_service)]\n");
writeFileSync(FIX + "/backend/app/services/other.py",
  "from app.models.user import User\ny = 2\nplain = 3\n");
process.chdir(FIX);
const pedit = (path, input) => handlers.tool_call({ toolName: "edit", input: { path, input } }, {});
check("9 patch replace of watched import BLOCK",
  pedit("backend/app/dependencies/services.py", "[backend/app/dependencies/services.py#AAAA]\nPUT 1.:\n+from app.services.notice import NoticeService")?.block === true);
check("10 patch insert alongside pass",
  pedit("backend/app/dependencies/services.py", "[backend/app/dependencies/services.py#AAAA]\nPUT 1+1@:\n+from app.services.notice import NoticeService") === undefined);
check("11 patch replace retaining the line pass",
  pedit("backend/app/dependencies/services.py", "[backend/app/dependencies/services.py#AAAA]\nPUT 1.:\n+from app.services.user import UserService\n+from app.services.notice import NoticeService") === undefined);
check("12 patch replace of plain line pass",
  pedit("backend/app/services/other.py", "[backend/app/services/other.py#AAAA]\nPUT 3.:\n+plain = 4") === undefined);
check("13 patch import swap in unwatched file BLOCK",
  pedit("backend/app/services/other.py", "[backend/app/services/other.py#AAAA]\nPUT 1.:\n+from app.models.notice import Notice")?.block === true);
check("14 patch Dep-alias replace BLOCK",
  pedit("backend/app/dependencies/services.py", "[backend/app/dependencies/services.py#AAAA]\nPUT 3.:\n+NoticeServiceDep = Annotated[NoticeService, Depends(get_notice_service)]")?.block === true);

// 15-19: universal sibling-swap boundary (no path list, no framework idiom)
writeFileSync(FIX + "/backend/app/services/generic.py",
  "app.state.user_service = UserService(session)\nx = 1\nresult = compute(y)\napp.mount(user_admin)\n");
check("15 sibling swap (2 identifier pairs) in unwatched file BLOCK",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 1.:\n+app.state.notice_service = NoticeService(session)")?.block === true);
check("15b sibling swap retained-elsewhere line updated in place",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 1.:\n+app.state.user_service = UserService(session, cache)") === undefined);
check("16 value modification pass",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 2.:\n+x = 2") === undefined);
check("17 single-identifier change pass",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 3.:\n+result = compute(z)") === undefined);
check("18 sibling swap retained alongside pass",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 1.:\n+self.registry.register(UserHandler)\n+self.registry.register(NoticeHandler)") === undefined);
check("19 등록 줄(mount) 교체는 BLOCK — 레지스트리 항목이 사라진다(2026-08-28 회귀 근거)",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 4.:\n+configure_admin_mounts(app)")?.block === true);
check("19b 비등록 줄의 형태 변경 재작성은 통과",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 3.:\n+result = compute_v2(y)") === undefined);

// 20-21: intent protocol — a declared replacement passes; the marker is edit-scoped
check("20 declared replace intent passes",
  pedit("backend/app/dependencies/services.py", "[backend/app/dependencies/services.py#AAAA]\nPUT 1.:\n+from app.services.notice import NoticeService\n+# intent: replace") === undefined);
check("21 undeclared sibling swap still blocked",
  pedit("backend/app/services/generic.py", "[backend/app/services/generic.py#AAAA]\nPUT 1.:\n+app.state.notice_service = NoticeService(session)")?.block === true);

// 23-24: fail-open — the guard must never crash the edit (EISDIR class, measured)
check("23 empty path fail-open",
  pedit("", "[x#AAAA]\nPUT 1.:\n+whatever") === undefined);
check("24 directory path fail-open",
  pedit("backend/app", "[backend/app#AAAA]\nPUT 1.:\n+whatever") === undefined);

// 25-26: '+' 접두 없는 PUT 본문(2026-08-28 배포 셀 실측 형식) — 같은 규칙이 걸려야 한다
writeFileSync(FIX + "/backend/app/main.py",
  "from app.routers import auth, batch, user\nx = 1\napi_router.include_router(user.router)\n");
check("25 접두 없는 교체형 형제치환 BLOCK",
  pedit("backend/app/main.py", "[backend/app/main.py#0D77]\nPUT 3:\napi_router.include_router(notice.router)")?.block === true);
check("26 접두 없는 삽입형은 통과",
  pedit("backend/app/main.py", "[backend/app/main.py#0D77]\nPUT 3+1@:\napi_router.include_router(notice.router)") === undefined);

process.exit(bad ? 1 : 0);
