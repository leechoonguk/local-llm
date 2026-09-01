// 푸시된 리비전 불변성 프루프 — strict-backend-migrations.ts 와 그것이 쓰는 정책
// (sandbox/.omp/hooks/lib/backend-migration-policy.ts).
//
// 두 구멍을 고정한다:
//  1) 경로 실명(失明) — 패치형 편집은 `path` 필드가 없고 대상이 패치 본문 첫 줄의 `[경로#TAG]`
//     헤더에만 있다. 그 모양을 안 읽으면 푸시된 리비전을 고치는 편집이 그대로 통과한다.
//  2) 채널 — 파일을 옮기고 지우는 것은 셸 동사만이 아니다. `eval` 본문의 `fs.renameSync()`·
//     `shutil.move()`·`os.remove()` 는 셸 동사가 하나도 없는 같은 행위다.
//
// 픽스처는 os.tmpdir() 아래 진짜 git 저장소 한 쌍(bare 원격 + 클론)이다 — 불변성 판정이
// 업스트림 조회이기 때문에 합성할 수 없다. 네트워크는 쓰지 않는다(로컬 경로 원격).
import { tmpdir } from "node:os";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const FIX = join(tmpdir(), "llm-bench-proof-fixtures", "migration-guard");
const REMOTE = join(FIX, "remote.git");
const WORK = join(FIX, "work");
const PUSHED = "backend/alembic/versions/0007_seed_notice.py";
const LOCAL = "backend/alembic/versions/0008_add_notice_column.py";

rmSync(FIX, { recursive: true, force: true });
mkdirSync(join(WORK, "backend", "app"), { recursive: true });
mkdirSync(join(WORK, "backend", "alembic", "versions"), { recursive: true });
writeFileSync(join(WORK, "backend", "app", "__init__.py"), "");
writeFileSync(join(WORK, PUSHED), 'revision = "0007"\n');

const git = (args, cwd = WORK) =>
  execFileSync("git", ["-c", "user.email=proof@example.invalid", "-c", "user.name=proof", ...args], {
    cwd,
    stdio: "pipe",
    encoding: "utf-8",
  });

execFileSync("git", ["init", "--bare", "--quiet", REMOTE], { stdio: "pipe" });
git(["-c", "init.defaultBranch=main", "init", "--quiet", "."]);
git(["checkout", "-q", "-B", "main"]);
git(["add", "-A"]);
git(["commit", "-q", "-m", "seed"]);
git(["remote", "add", "origin", REMOTE]);
git(["push", "-q", "-u", "origin", "main"]);
// 로컬에만 있는(아직 안 올린) 리비전 — 편집 가능해야 한다.
writeFileSync(join(WORK, LOCAL), 'revision = "0008"\n');

process.chdir(WORK); // 정책 모듈은 import 시점에 프로젝트 루트를 잡는다

let bad = 0;
const check = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) bad++; };
const blocked = (r) => !!r && r.block === true;

let handler;
const mod = await import(pathToFileURL(join(REPO, "sandbox/.omp/hooks/pre", "strict-backend-migrations.ts")).href);
mod.default({ on: (_event, fn) => { handler = fn; } });
const call = (toolName, input) => handler({ toolName, input }, {});

// --- 경로 해석: 세 모양 전부 같은 파일을 가리킨다 ---
check("M1 path 없이 패치 헤더만 있어도 푸시된 리비전 편집은 BLOCK",
  blocked(call("edit", { input: `[${PUSHED}#AB12]\nPUT 1.:\nrevision = "0007b"` })));
check("M2 내용 태그가 붙은 path 도 동일하게 BLOCK",
  blocked(call("edit", { path: `${PUSHED}#AB12`, input: 'PUT 1.:\nrevision = "0007b"' })));
check("M3 깨끗한 path 도 물론 BLOCK", blocked(call("edit", { path: PUSHED })));
check("M4 아직 안 올린 리비전은 편집 가능(헤더 경로로도)",
  !blocked(call("edit", { input: `[${LOCAL}#AB12]\nPUT 1.:\nrevision = "0008b"` })));
check("M5 마이그레이션이 아닌 파일은 이 가드의 대상이 아니다",
  !blocked(call("edit", { input: "[backend/app/main.py#AB12]\nPUT 1.:\nx = 1" })));
check("M6 경로를 어디서도 못 읽으면 fail-open — 훅은 도구 호출을 죽이지 않는다",
  !blocked(call("edit", { input: 'PUT 1.:\nrevision = "x"' })));
check("M7 리비전 파일을 손으로 만드는 write 는 BLOCK(번호는 migrate-gen 이 매긴다)",
  blocked(call("write", { path: "backend/alembic/versions/0009_hand_made.py" })));
// --- pi-hashline-edit-pro 편집 툴(2026-09-01): 평문 input.path 만 싣는다 — 우회 실측 후 고정 ---
check("M7a 플러그인 replace 로 푸시된 리비전 편집은 BLOCK",
  blocked(call("replace", { path: PUSHED, remove_from: "AB12", remove_to: "AB12", replacement_lines: 'revision = "0007b"' })));
check("M7b 플러그인 insert 도 동일하게 BLOCK",
  blocked(call("insert", { path: PUSHED, anchor: "AB12", lines: "x = 1" })));
check("M7c 플러그인 undo_last_change 도 리비전 파일이면 BLOCK",
  blocked(call("undo_last_change", { path: PUSHED })));
check("M7d 아직 안 올린 리비전은 replace 로 편집 가능",
  !blocked(call("replace", { path: LOCAL, remove_from: "AB12", remove_to: "AB12", replacement_lines: 'revision = "0008b"' })));

// --- 채널: 파일을 옮기고 지우는 것은 셸 동사만이 아니다 ---
check("M8 셸 mv 는 여전히 BLOCK(기존 동사 회귀 없음)",
  blocked(call("bash", { command: `mv ${PUSHED} backend/alembic/versions/0007_renamed.py` })));
check("M9 eval 본문의 fs.renameSync 도 같은 행위",
  blocked(call("eval", { code: `fs.renameSync("${PUSHED}", "backend/alembic/versions/0007_renamed.py")` })));
check("M10 shutil.move 도 마찬가지",
  blocked(call("eval", { code: `shutil.move("${PUSHED}", "/tmp/keep.py")` })));
check("M11 os.remove 도 마찬가지",
  blocked(call("eval", { code: `os.remove("${PUSHED}")` })));
check("M12 os.rename 도 마찬가지",
  blocked(call("eval", { code: `os.rename("${PUSHED}", "backend/alembic/versions/0007_x.py")` })));
check("M13 writeFileSync 로 덮어쓰는 것도 재작성이다",
  blocked(call("eval", { code: `fs.writeFileSync("${PUSHED}", "revision = '0007b'")` })));
check("M14 fs.unlinkSync 도 마찬가지",
  blocked(call("eval", { code: `fs.unlinkSync("${PUSHED}")` })));
check("M15 읽기는 막지 않는다 — 무엇을 했는지 아는 유일한 방법이다",
  !blocked(call("bash", { command: `cat ${PUSHED}` })));
check("M16 아직 안 올린 리비전은 옮겨도 된다",
  !blocked(call("eval", { code: `fs.renameSync("${LOCAL}", "backend/alembic/versions/0008_renamed.py")` })));

console.log(bad ? `\n${bad} FAILED` : "\nall green");
process.exit(bad ? 1 : 0);
