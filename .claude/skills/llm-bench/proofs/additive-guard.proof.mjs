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

// 27-33: 이 가드가 실제로 도는 경로들 — 전수 점검(2026-08-30)에서 편집 2,923건 중 2,670건이
// fail-open 으로 빠져 무동작이었다(path 없음 2,230 / 내용 태그 440). 문법에도 두 구멍이 있었다:
// 범위 교체 `PUT N.=M:` 1,109건, 삭제 `CUT` 154건.
writeFileSync(FIX + "/backend/app/main.py",
  "from app.routers import auth, batch, user\nx = 1\napi_router.include_router(user.router)\napi_router.include_router(batch.router)\n");
const pedit2 = (input, path) => handlers.tool_call({ toolName: "edit", input: path === undefined ? { input } : { path, input } }, {});

check("27 path 없이 헤더만 있어도 등록 줄 교체 BLOCK",
  pedit2("[backend/app/main.py#AB12]\nPUT 3:\napi_router.include_router(notice.router)")?.block === true);
check("28 내용 태그가 붙은 path 도 동일하게 BLOCK",
  pedit2("PUT 3:\napi_router.include_router(notice.router)", "backend/app/main.py#AB12")?.block === true);
check("29 범위 교체(PUT N.=M:)가 등록 줄을 삼키면 BLOCK",
  pedit2("[backend/app/main.py#AB12]\nPUT 3.=4:\napi_router.include_router(notice.router)")?.block === true);
check("30 CUT 으로 import 줄 삭제 BLOCK",
  pedit2("[backend/app/main.py#AB12]\nCUT 1")?.block === true);
check("31 CUT 으로 평범한 줄 삭제는 통과",
  pedit2("[backend/app/main.py#AB12]\nCUT 2") === undefined);
check("32 의도 선언은 범위 교체도 통과",
  pedit2("[backend/app/main.py#AB12]\n# intent: replace\nPUT 3.=4:\napi_router.include_router(notice.router)") === undefined);
check("33 읽을 수 없는 경로는 여전히 fail-open(던지지 않는다)",
  pedit2("PUT 1:\nx", "/nonexistent/dir/") === undefined);

// 34-35: write 경로에도 내용 태그가 붙어 올 수 있다. 벗기지 않으면 확장자 판정이 빗나가
// 통째 덮어쓰기가 조용히 통과한다(가드가 있는데 아무 일도 안 하는 그 상태).
writeFileSync(FIX + "/backend/app/services/big.py",
  Array.from({ length: 20 }, (_, i) => `line_${i} = compute_${i}()`).join("\n") + "\n");
const pwrite = (path, content) => handlers.tool_call({ toolName: "write", input: { path, content } }, {});
check("34 태그 붙은 write 경로도 통째 덮어쓰기 BLOCK",
  pwrite("backend/app/services/big.py#0D77", "x = 1\n")?.block === true);
check("35 기존 내용을 유지한 write 는 통과",
  pwrite("backend/app/services/big.py#0D77",
    Array.from({ length: 20 }, (_, i) => `line_${i} = compute_${i}()`).join("\n") + "\nline_20 = compute_20()\n") === undefined);

// 37-43: 판정은 "같은가"가 아니라 "잃었는가"다. 한 줄짜리 import 목록에 이름을 더하려면 그 줄을
// 고칠 수밖에 없으므로, 글자 동일성을 요구하면 정당한 배선이 통째로 막힌다 — 실측(2026-08-30)에서
// 세션이 라우터 등록 단계에서 갇혔고, 안내문("나란히 추가하라")은 실행 불가능한 지시였다.
writeFileSync(FIX + "/backend/app/main.py",
  "from app.routers import auth, batch, health, integration, user\napi_router.include_router(user.router)\napi_router.include_router(batch.router)\n");
const wire = (input) => handlers.tool_call({ toolName: "edit", input: { input } }, {});
const M = "backend/app/main.py";

check("37 import 목록에 이름 추가는 통과(범위형)",
  wire(`[${M}#A]\nPUT 1.=1:\nfrom app.routers import auth, batch, health, integration, notice, user`) === undefined);
check("38 import 목록에 이름 추가는 통과(단일행형)",
  wire(`[${M}#A]\nPUT 1:\nfrom app.routers import auth, batch, health, integration, notice, user`) === undefined);
check("39 등록 줄 삽입은 통과",
  wire(`[${M}#A]\nPUT 2+1@:\napi_router.include_router(notice.router)`) === undefined);
check("40 등록 대상 바꿔치기는 BLOCK(user.router 가 사라진다)",
  wire(`[${M}#A]\nPUT 2.=2:\napi_router.include_router(notice.router)`)?.block === true);
check("41 import 목록 축소는 BLOCK",
  wire(`[${M}#A]\nPUT 1.=1:\nfrom app.routers import notice`)?.block === true);
check("42 CUT 으로 등록 줄 삭제는 BLOCK",
  wire(`[${M}#A]\nCUT 2`)?.block === true);
check("43 의도 선언이면 교체도 통과",
  wire(`[${M}#A]\n# intent: replace\nPUT 2.=2:\napi_router.include_router(notice.router)`) === undefined);

process.exit(bad ? 1 : 0);
