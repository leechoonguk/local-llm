/**
 * llm-bench 2단계 러너 — sandbox/ 에서 로컬 모델에게 실제 과제를 시키고 게이트로 채점한다.
 *
 * 피험자는 `sandbox/`(fast-api-standard 를 batch/user 도메인만 남긴 최소 baseline, 포트 분리)에서 돈다.
 * sandbox 는 git 저장소가 아니다 — local-llm 저장소가 파일을 추적하고, 원복은 부모 저장소의
 * `git checkout -- sandbox && git clean -fdq sandbox` 다. 임시 git 은 만들지 않는다.
 *
 * 현재 과제는 REST(Mode B, notice CRUD) 하나다. integration(Mode A)은 sandbox 에서 서브시스템째
 * 제거했다(계약 테스트가 시드 마이그레이션을 리플레이해 결합이 컸다). 레퍼런스 패치는
 * `reference/` 에 보존돼 있으니, integration 을 sandbox 에 되살리면 Mode A 를 다시 붙일 수 있다.
 *
 * 사용:
 *   node .claude/skills/llm-bench/runner.ts --dry-run                          # 세팅→채점→원복만, 모델 없이
 *   node .claude/skills/llm-bench/runner.ts --model omlx/…Qwen3.6…:mtp --campaign omlx-3.6
 *   node .claude/skills/llm-bench/runner.ts --models a,b --campaign <name> --timeout 2700 [--restart-omlx]
 *   node .claude/skills/llm-bench/runner.ts --matrix                           # DEFAULT_MODELS
 *   node .claude/skills/llm-bench/runner.ts --revert-only                      # 중단된 셀 뒤처리
 */
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { homedir, tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKSPACE = resolve(HERE, "..", "..", "..");
const SANDBOX = join(WORKSPACE, "sandbox");
const BENCH = join(WORKSPACE, "bench");
const TASKS_DIR = join(HERE, "tasks");
const REFERENCE_DIR = join(HERE, "reference");
const SESSIONS = join(homedir(), ".omp", "agent", "sessions");
const OMLX_URL = "http://127.0.0.1:9090";

interface Task {
  mode: "A" | "B";
  spec: string;
  /** Mode A: 레퍼런스 식별자. reference/<ref>.manifest.json + <ref>.parent.patch 가 있어야 한다. */
  reference?: string;
  expect: number;
  prompt: (spec: string) => string;
}

const TASKS: Record<string, Task> = {
  integration: {
    mode: "A",
    spec: "integration_spec.md",
    reference: "a1aebf3",
    expect: 6,
    prompt: (spec) => `Add the 바코드연계 품목정보 API (service I2570) to this repository.

1. Read the skill first: .omp/skills/integration/SKILL.md. Follow it.
2. Read ${spec} — the measurement is already done, do NOT call any live API.
3. Model your work on the existing sibling operation \`search-food-raw-material\`:
   its seed migrations, api/integration.search-food-raw-material.http, and its contract fixture.
4. Reuse the seeded provider \`mfds-food-safety-korea\` and its \`service-key\` secret. Do not seed a new provider.
5. Deliverables: the seed migration(s) for the operation and its fields, the api/*.http request file,
   the recorded fixture, and the test wiring the sibling has.
6. Finish by running \`make verify\` and make it pass.`,
  },
  rest: {
    mode: "B",
    spec: "rest_spec.md",
    expect: 13,
    prompt: (spec) => `Add a \`notice\` (공지사항) CRUD domain to this repository.

1. Read the domain rule first: .omp/rules/backend-domain.md. Follow it.
2. Read ${spec} — that is the requirement.
3. Model your work on the existing sibling domain \`batch\`: backend/app/models/batch.py,
   backend/app/schemas/batch.py, backend/app/repositories/batch.py, backend/app/services/batch.py,
   backend/app/routers/batch.py, backend/tests/{api,repositories,services}/test_batch.py, api/batch.http.
4. Reuse the existing authentication dependency and the existing pagination convention.
   Do not add a new auth mechanism and do not seed a new account.
5. Deliverables: the five domain layers, the dependency wiring and router registration,
   the Alembic migration for the table, the request file, and the tests the sibling has.
6. Finish by running \`make verify\` and make it pass.`,
  },
};

/** --matrix 의 기본 후보. 현재 서빙(oMLX)에 등록된 코더 — omp/models.yml 참고. */
const DEFAULT_MODELS = [
  "omlx/mlx-community--Qwen3.6-35B-A3B-5bit:mtp",
  "omlx/mlx-community--Qwen3.8-27B-nvfp4:mtp",
];

/** aux(tiny/smol) 역할 고정 대상. 실사용 구성의 4B — 벤치도 이걸로 검증한다(omp/config.fragment.yml). */
const AUX_MODEL = "omlx/mlx-community--Qwen3.5-4B-4bit";

function sh(cmd: string, args: string[], cwd = SANDBOX, timeout = 900_000): { code: number; out: string } {
  const r = spawnSync(cmd, args, { cwd, encoding: "utf-8", timeout });
  return { code: r.status ?? 1, out: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}
const gitWs = (args: string[]): string => sh("git", args, WORKSPACE).out.trim();
const make = (target: string, dir = SANDBOX): { code: number; out: string } => sh("make", [target], dir);

// ---------------------------------------------------------------- 세팅 / 원복

/** baseline 시점 sandbox 에 존재하는 도메인 모델 파일명 집합(회귀 판정용). git 불필요. */
function baselineModels(): Set<string> {
  const dir = join(SANDBOX, "backend", "app", "models");
  if (!existsSync(dir)) return new Set();
  return new Set(
    readdirSync(dir)
      .filter((f) => f.endsWith(".py"))
      .map((f) => f.replace(/\.py$/, ""))
      .filter((n) => n !== "__init__" && n !== "base"),
  );
}

/** 부모 저장소 기준으로 sandbox 가 깨끗한지. 추적 파일 변경이 있으면 원복이 지우므로 거부한다. */
function assertSandboxClean(): void {
  if (gitWs(["ls-files", "--", "sandbox"]).length === 0) {
    console.error("refusing to run: sandbox/ is not tracked by the workspace repo (git add sandbox first).");
    process.exit(2);
  }
  if (existsSync(join(SANDBOX, ".git"))) {
    console.error("refusing to run: sandbox/.git exists (a stray git repo). Remove it: rm -rf sandbox/.git");
    process.exit(2);
  }
  // 워크트리 열(2번째 글자)이 비어 있지 않으면 미커밋 변경이다. 스테이징만 된 추가(`A `)는 허용.
  const dirty = gitWs(["status", "--porcelain", "--", "sandbox"]).split("\n").filter((l) => l.trim() && !l.startsWith("??") && l[1] !== " ");
  if (dirty.length > 0) {
    console.error("refusing to run: sandbox/ has uncommitted tracked changes, and revert() would destroy them:");
    for (const line of dirty) console.error(`  ${line}`);
    process.exit(2);
  }
}

/** Mode A: 레퍼런스 산출물을 지우고 수정 파일을 부모 상태로 되돌린다(파일 연산 + 역패치, git 불필요). */
function toParentState(ref: string): void {
  const manifest = JSON.parse(readFileSync(join(REFERENCE_DIR, `${ref}.manifest.json`), "utf-8")) as {
    added: string[]; modified: string[];
  };
  for (const f of manifest.added) rmSync(join(SANDBOX, f), { force: true });
  const patch = join(REFERENCE_DIR, `${ref}.parent.patch`);
  const r = sh("git", ["apply", "--directory=sandbox", patch], WORKSPACE);
  if (r.code !== 0) throw new Error(`parent patch failed: ${r.out}`);
}

/** baseline 테스트 트리 스냅샷(assert 삭제 집계용 — sandbox 에 git 이 없으므로). */
function snapshotTests(): string {
  const dst = mkdtempSync(join(tmpdir(), "llm-bench-tests-"));
  cpSync(join(SANDBOX, "backend", "tests"), join(dst, "tests"), { recursive: true });
  return dst;
}

function setup(task: Task): { baseline: number; baselineOut: string; models: Set<string>; snapshot: string } {
  assertSandboxClean();
  if (task.mode === "A" && task.reference) toParentState(task.reference);
  const snapshot = snapshotTests();
  const models = baselineModels();
  const db = make("db-init");
  if (db.code !== 0) console.error(db.out.split("\n").slice(-10).join("\n"));
  const v = make("verify");
  return { baseline: v.code, baselineOut: v.out, models, snapshot };
}

function revert(): void {
  gitWs(["checkout", "--", "sandbox"]);
  gitWs(["clean", "-fdq", "--", "sandbox"]);
  make("db-init");
}

// ---------------------------------------------------------------- 모델 상주

function unloadOllama(): void {
  const lines = sh("ollama", ["ps"], WORKSPACE).out.trim().split("\n").slice(1);
  for (const line of lines) {
    const name = line.trim().split(/\s+/)[0];
    if (name) sh("ollama", ["stop", name], WORKSPACE);
  }
}

/**
 * oMLX 앱 서버가 준비됐는지 확인한다. **서버를 재시작하지 않는다** — `omlx start/restart` 는 brew services
 * 또는 별도 headless 서버라 GUI 앱(oMLX.app)과 충돌하고 규칙 6 위반이며, 앱 서버는 CLI 로 재시작할 수 없다.
 * 셀 간 모델 정리는 서버 재시작 대신 oMLX 자체 관리(메모리 가드 LRU 축출)에 맡기고, `residency()` 로 검증한다.
 * (오MLX 는 단일 모델 언로드 API 를 노출하지 않는다 — 2026-08-25 실측: /unload·/eject 404.)
 */
function ensureServer(): void {
  const code = sh("curl", ["-s", "-o", "/dev/null", "-w", "%{http_code}", `${OMLX_URL}/v1/models`], WORKSPACE, 5_000).out.trim();
  if (code !== "200") throw new Error(`oMLX 서버가 :9090 에 없다(http=${code}) — oMLX.app 메뉴바에서 Start 후 재실행`);
  // 앱 관리 서버인지(부모가 oMLX.app) — brew/headless 서버면 측정 일관성이 깨지므로 경고.
  const parent = sh("bash", ["-c", "p=$(pgrep -f omlx-server | head -1); [ -n \"$p\" ] && ps -o command= -p $(ps -o ppid= -p $p | tr -d ' ') 2>/dev/null"], WORKSPACE, 5_000).out;
  if (parent && !/oMLX\.app/.test(parent)) console.error(`  !! oMLX 서버가 앱 관리가 아니다(부모: ${parent.trim().slice(0, 40)}) — 앱 메뉴바 서버로 검증할 것`);
}

/** omlx/ 접두사를 뗀 서버 모델 id (프로파일 포함): `omlx/mlx-…-5bit:mtp` → `mlx-…-5bit:mtp`. */
const omlxId = (model: string): string => model.replace(/^omlx\//, "");

const OMLX_ADMIN = "http://127.0.0.1:9090/admin/api";

/** oMLX 앱의 admin API 에서 지금 로드된(loaded:true) 모델 id 목록. skip_api_key_verification 로 루프백 무인증. */
function omlxLoadedModels(): string[] {
  const out = sh("curl", ["-s", "--max-time", "6", `${OMLX_ADMIN}/models`], WORKSPACE, 8_000).out;
  try {
    const d = JSON.parse(out) as { models?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>;
    const models = Array.isArray(d) ? d : (d.models ?? []);
    return models.filter((m) => m.loaded === true).map((m) => String(m.id));
  } catch { return []; }
}

/** 로드된 모델을 전부 언로드해 클린 슬레이트를 만든다 — 셀 시작 전 호출(강제 단일 상주). 앱 서버 유지, brew 아님. */
function omlxUnloadAll(): void {
  for (const id of omlxLoadedModels()) {
    sh("curl", ["-s", "-o", "/dev/null", "--max-time", "30", "-X", "POST", `${OMLX_ADMIN}/models/${id}/unload`], WORKSPACE, 35_000);
  }
}

/**
 * 상주 기록/검증. 보장은 **구성상** 성립한다 — 셀마다 서버를 재시작(전체 언로드)하고, default=대상 코더,
 * tiny/smol=4B aux 로 고정하며, compaction 은 같은 계열 :nothink 다. 그래서 로드될 수 있는 물리 모델은
 * {대상 코더, 그 드래프터, 4B aux} 셋뿐이고 엉뚱한 코더는 못 뜬다. 여기서는 그 사실을 기록하고,
 * 상주 수가 예상 범위(1~3)를 벗어나면 경고한다(재시작 실패·설정 누락의 신호). ok=false 면 재실행.
 */
function residency(model: string): Record<string, unknown> | null {
  if (model.startsWith("omlx/")) {
    // admin API 의 권위 있는 loaded 상태로 검증 — 개수만이 아니라 정체까지.
    const loaded = omlxLoadedModels();
    const coder = omlxId(model).split(":")[0];        // 프로파일 접미사 제거 → 물리 모델 id
    const aux = omlxId(AUX_MODEL).split(":")[0];
    // 예상 로드: 대상 코더, 그 드래프터(...-MTP-...), 4B aux 뿐. 그 밖의 코더가 있으면 이전 셀 잔재 = 오염.
    const unexpected = loaded.filter((m) => m !== coder && m !== aux && !/MTP/.test(m));
    return { server: "omlx", loaded_models: loaded, coder, aux, ok: loaded.includes(coder) && unexpected.length === 0 };
  }
  if (model.startsWith("ollama/")) {
    const coder = model.replace(/^ollama\//, "").replace(/:latest$/, "");
    const lines = sh("ollama", ["ps"], WORKSPACE).out.trim().split("\n").slice(1).filter((l) => l.trim());
    const loaded = lines.map((l) => l.trim().split(/\s+/)[0].replace(/:latest$/, ""));
    return { server: "ollama", loaded_count: lines.length, loaded, coder, ps: lines, ok: loaded.includes(coder) && loaded.every((n) => n === coder || n === omlxId(AUX_MODEL)) };
  }
  return null;
}

// ---------------------------------------------------------------- 채점

function newestSessionAfter(afterMs: number): string | null {
  let best: string | null = null;
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.name.endsWith(".jsonl") && statSync(p).mtimeMs > afterMs) {
        if (best === null || statSync(p).mtimeMs > statSync(best).mtimeMs) best = p;
      }
    }
  };
  if (existsSync(SESSIONS)) walk(SESSIONS);
  return best;
}

/** 세션 로그의 turns/toolCalls/loops/compactions/peak, 그리고 툴 종류별 횟수(write/edit 포함). */
function sessionMetrics(path: string | null): Record<string, unknown> {
  const m: Record<string, unknown> = { session: path, turns: null, toolCalls: null, loops: null, compactions: null, peak: null, writes: 0, tools: {} };
  if (path === null || !existsSync(path)) return m;
  const tools: Record<string, number> = {};
  for (const line of readFileSync(path, "utf-8").split("\n")) {
    if (line.includes('"continuity')) {
      try {
        const d = (JSON.parse(line).data ?? {}) as Record<string, unknown>;
        for (const k of ["turns", "toolCalls", "compactions"]) m[k] = d[k] ?? null;
        m.loops = Array.isArray(d.loops) ? d.loops.length : null;
        m.peak = d.lastUsage ?? null;
      } catch { /* 잘린 레코드는 지표가 아니다 */ }
    }
    for (const hit of line.matchAll(/"name"\s*:\s*"(read|write|edit|bash|glob|grep|ls)"/g)) tools[hit[1]] = (tools[hit[1]] ?? 0) + 1;
  }
  m.writes = (tools.write ?? 0) + (tools.edit ?? 0);
  m.tools = tools;
  return m;
}

/**
 * FAIL 행이 baseline 에 이미 있던 도메인(모델 파일이 있던 이름)이나 `remove_*` 를 가리키면 회귀,
 * 새로 만드는 도메인이면 미완성. 관측된 두 FAIL 모양에 대한 휴리스틱이다.
 */
function classifyFailures(out: string, models: Set<string>): { regressions: string[]; incomplete: string[] } {
  const lines = (out.match(/^\s*FAIL:.*$/gm) ?? []).map((l) => l.trim());
  const regressions: string[] = [];
  const incomplete: string[] = [];
  for (const line of lines) {
    const domain = line.match(/^FAIL:\s*([a-z][a-z0-9_]*):/)?.[1];
    if (/remove_(table|index|column)/.test(line) || (domain && models.has(domain))) regressions.push(line);
    else incomplete.push(line);
  }
  return { regressions, incomplete };
}

function grade(task: Task, models: Set<string>, snapshot: string): Record<string, unknown> {
  const files = gitWs(["status", "--porcelain", "--", "sandbox/api", "sandbox/backend"]).split("\n").filter((l) => l.trim());
  const { code, out } = make("verify");
  const { regressions, incomplete } = classifyFailures(out, models);
  // baseline 스냅샷 대비 지워진 assert 행 수(sandbox 에 git 이 없으므로 --no-index diff).
  const removed = sh("bash", ["-c",
    `git --no-pager diff --no-index --no-color '${join(snapshot, "tests")}' '${join(SANDBOX, "backend", "tests")}' | sed -n '/^-[^-].*assert/p' | wc -l`], WORKSPACE).out;
  const leak = task.reference
    ? (JSON.parse(readFileSync(join(REFERENCE_DIR, `${task.reference}.manifest.json`), "utf-8")) as { added: string[] }).added
    : [];
  return {
    artifacts: files.length,
    expected: task.expect,
    files,
    gate_exit: code,
    gate_failures: (out.match(/^\s*FAIL:/gm) ?? []).length,
    regressions: regressions.length,
    regression_detail: regressions,
    incomplete_failures: incomplete.length,
    asserts_removed: Number.parseInt(String(removed ?? "0").trim(), 10) || 0,
    omp_touched: gitWs(["status", "--porcelain", "--", "sandbox/.omp", "sandbox/Makefile"]).split("\n").filter((l) => l.trim()).length,
    reference_names_reused: leak.filter((f) => files.some((l) => l.includes(f.split("/").pop() ?? " "))),
  };
}

// ---------------------------------------------------------------- 셀 하나

async function one(model: string, taskName: string, opts: { timeoutS: number; dryRun: boolean; restartOmlx: boolean }): Promise<Record<string, unknown>> {
  const task = TASKS[taskName];
  const spec = join(TASKS_DIR, task.spec);
  console.log(`\n===== ${model || "(dry-run)"} / ${taskName} (mode ${task.mode}, cap ${opts.timeoutS}s)`);

  const { baseline, baselineOut, models, snapshot } = setup(task);
  if (baseline !== 0) {
    console.error(baselineOut.split("\n").filter((l) => /FAIL|Error|error/.test(l)).slice(0, 20).join("\n"));
    rmSync(snapshot, { recursive: true, force: true });
    revert();
    return { model, task: taskName, error: "baseline not green" };
  }
  console.log("  baseline green");

  if (opts.dryRun) {
    const row = { model: "(dry-run)", task: taskName, mode: task.mode, wall_s: 0, timed_out: false, ...grade(task, models, snapshot) };
    rmSync(snapshot, { recursive: true, force: true });
    revert();
    return row;
  }

  // 로컬 모델: omlx 는 앱 서버 준비 확인(재시작 안 함 — oMLX 자체 LRU 축출 + residency 검증에 의존),
  // ollama 는 다른 모델 stop. 대상만 상주하는지는 셀 종료 시 residency() 로 검사한다.
  const local = model.startsWith("omlx/") || model.startsWith("ollama/");
  if (model.startsWith("omlx/")) { ensureServer(); omlxUnloadAll(); } // 앱 서버 확인 + 로드된 모델 전부 언로드(강제 클린 슬레이트)
  if (model.startsWith("ollama/")) unloadOllama();

  // aux 역할 고정: tiny/smol 을 **실제 4B aux 모델**로 고정한다(코더가 아니다 — 실사용 구성으로 검증).
  // 이렇게 하면 셀 동안 로드될 수 있는 물리 모델은 {대상 코더(--model), 그 :mtp 드래프터(같은 계열),
  // 4B aux} 로 한정된다 — 깨끗한 재시작(위)과 합쳐 **구성상** 엉뚱한 코더가 상주할 수 없다.
  // 코더 자체 설정(thinking·샘플링)은 불변. compaction 은 models.yml 에서 같은 계열 :nothink.
  let overlayDir: string | null = null;
  const extra: string[] = [];
  if (local) {
    overlayDir = mkdtempSync(join(tmpdir(), "llm-bench-cfg-"));
    writeFileSync(join(overlayDir, "overlay.yml"), `modelRoles:\n  tiny: ${AUX_MODEL}\n`);
    extra.push("--config", join(overlayDir, "overlay.yml"), "--smol", AUX_MODEL);
  }

  const started = Date.now();
  const child = spawn("omp", ["-p", task.prompt(spec), "--model", model, ...extra], { cwd: SANDBOX, stdio: "ignore", detached: true });
  let timedOut = false;
  const killGroup = (signal: string): void => { spawnSync("kill", [`-${signal}`, `-${child.pid}`], { encoding: "utf-8" }); };
  await new Promise<void>((resolveP) => {
    const timer = setTimeout(() => {
      timedOut = true;
      killGroup("TERM");
      setTimeout(() => { killGroup("KILL"); resolveP(); }, 60_000);
    }, opts.timeoutS * 1000);
    child.on("exit", () => { clearTimeout(timer); resolveP(); });
  });
  const wall = Math.round((Date.now() - started) / 1000);

  const res = residency(model);
  if (overlayDir) rmSync(overlayDir, { recursive: true, force: true });
  if (res && res.ok === false) console.error(`  !! residency: loaded_count=${res.loaded_count} (예상 코더+4B aux) — 재시작/역할 고정 확인 후 재실행`);
  const row: Record<string, unknown> = {
    model, task: taskName, mode: task.mode, wall_s: wall, timed_out: timedOut,
    residency: res,
    ...grade(task, models, snapshot),
    ...sessionMetrics(newestSessionAfter(started)),
  };
  // writes 0 = 피험자가 아무것도 안 썼다. Mode A 는 부모 상태 잔여 산출물 때문에 artifacts>0·gate 0
  // 으로 "성공처럼" 보일 수 있으니, 게이트와 무관하게 실패로 표시한다(no_work).
  row.no_work = (row.writes ?? 0) === 0;
  if (row.no_work) console.error(`  !! no_work: writes 0 — 피험자가 산출 없음(게이트/산출물 수와 무관하게 실패)`);
  rmSync(snapshot, { recursive: true, force: true });
  revert();
  console.log(`  -> ${row.artifacts}/${row.expected} artifacts, gate exit ${row.gate_exit} ` +
    `(${row.gate_failures} FAIL: ${row.regressions} regression, ${row.incomplete_failures} incomplete), ` +
    `writes ${row.writes}, ${wall}s${timedOut ? " TIMEOUT" : ""}`);
  return row;
}

// ---------------------------------------------------------------- main

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const arg = (name: string): string | undefined => { const i = argv.indexOf(name); return i === -1 ? undefined : argv[i + 1]; };
  const has = (name: string): boolean => argv.includes(name);

  if (has("--revert-only")) { revert(); console.log("reverted"); return; }

  const timeoutS = Number.parseInt(arg("--timeout") ?? "2700", 10);
  const dryRun = has("--dry-run");
  const models = dryRun ? [""] : has("--matrix") ? DEFAULT_MODELS : (arg("--models") ?? arg("--model") ?? "").split(",").filter(Boolean);
  const tasks = (arg("--tasks") ?? arg("--task") ?? "integration,rest").split(",").filter(Boolean);
  if (models.length === 0 || tasks.some((t) => !(t in TASKS))) {
    console.error(`usage: --model <id> [--task integration|rest] | --models a,b | --matrix | --dry-run   (tasks: ${Object.keys(TASKS).join(", ")})`);
    process.exit(2);
  }

  const today = new Date().toISOString().slice(0, 10);
  const campaign = arg("--campaign") ?? (dryRun ? "dry-run" : (models[0] || "x").replace(/^[a-z]+\//, "").replace(/[^A-Za-z0-9.]+/g, "-").toLowerCase());
  const resultsPath = join(BENCH, `${today}.s2.${campaign}.json`);
  mkdirSync(BENCH, { recursive: true });
  let rows: Array<Record<string, unknown>> = [];
  if (existsSync(resultsPath)) {
    try { const prior: unknown = JSON.parse(readFileSync(resultsPath, "utf-8")); if (Array.isArray(prior)) rows = prior as Array<Record<string, unknown>>; }
    catch { /* 깨진 로그는 덮는다 */ }
  }

  for (const model of models) {
    for (const task of tasks) {
      const at = new Date().toISOString();
      try {
        rows.push({ at, ...(await one(model, task, { timeoutS, dryRun, restartOmlx: has("--restart-omlx") })) });
      } catch (error: unknown) {
        console.error(`  !! ${model}/${task}: ${String(error)}`);
        revert();
        rows.push({ at, model, task, error: String(error) });
      }
      if (!dryRun) writeFileSync(resultsPath, JSON.stringify(rows, null, 1));
    }
  }
  if (dryRun) console.log(`\ndry-run ok (nothing written): ${JSON.stringify(rows[rows.length - 1])}`);
  else console.log(`\nwrote ${resultsPath} (${rows.length} rows total)`);
}

void main();
