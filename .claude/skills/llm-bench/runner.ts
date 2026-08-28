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
    expect: 15, // 실측 재보정(2026-08-27 4자 토의): 초록 셀 산출물이 일관되게 15-16 — 13은 만성 과대달성으로 읽혀 미달 감지 불능
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
   The request file must also be listed in tests/core/test_seed_api_actor.py's expected
   http files — add it alongside the existing entries.
6. Finish by running \`make verify\` and make it pass.`,
    // 과제 텍스트 v1.1(2026-08-28 라운드 3): seed_api_actor 기대는 게이트 계약이라 스펙에
    // 명시(게이트 관점 "spec completeness" 판정, 실측 7.8m/2.5m 소모 — 숨은 게이트였다).
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
  const m: Record<string, unknown> = { session: path, turns: null, toolCalls: null, loops: null, compactions: null, peak: null, writes: 0, tools: {}, gate_runs: 0, first_full_gate_s: null };
  if (path === null || !existsSync(path)) return m;
  const tools: Record<string, number> = {};
  // 연속 지표(4자 토의 라운드 2, 2026-08-28): full-gate 실행 횟수·첫 실행 시각 —
  // p̂=12.5% 기준선에서 binary green 은 무력하므로 암 판정은 이 연속 지표로 한다.
  let t0: number | null = null;
  let gateRuns = 0;
  let firstGateS: number | null = null;
  let firstGreenS: number | null = null;
  const FULL_GATE = /make(?:\\?["'\s][^"]{0,40})?\s*(?:-C\s+\S+\s+)?(?:verify|test)(?!-fast)\b/;
  for (const line of readFileSync(path, "utf-8").split("\n")) {
    const ts = line.match(/"timestamp"\s*:\s*"([^"]+)"/)?.[1];
    if (ts && t0 === null) t0 = Date.parse(ts);
    // dedupe: 도구 호출은 세션에 3중(assistant echo/tool_execution_start/toolResult)으로
    // 반영되고 continuity 스냅샷이 이력을 재포함한다(실측: writes 723 vs 진짜 26).
    // toolResult 레코드만, continuity 라인 제외로 계수한다.
    const isResultLine = /"role"\s*:\s*"toolResult"/.test(line) && !line.includes('"continuity');
    if (isResultLine && /"toolName"\s*:\s*"bash"/.test(line) && FULL_GATE.test(line)) {
      gateRuns++;
      if (firstGateS === null && ts && t0 !== null) firstGateS = Math.round((Date.parse(ts) - t0) / 1000);
    }
    // 첫 full-suite 초록(중앙값 지표의 시각원 — 라운드 3 채점 요건): 커버리지 게이트
    // 통과 문구는 full 게이트 초록에서만 나온다.
    if (firstGreenS === null && isResultLine && line.includes("Required test coverage of 100% reached") && ts && t0 !== null) {
      firstGreenS = Math.round((Date.parse(ts) - t0) / 1000);
    }
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
  m.gate_runs = gateRuns;            // 계수만 하고 되쓰기를 빠뜨렸던 버그(refrozen 블록 실측) 수정
  m.first_full_gate_s = firstGateS;
  m.first_green_s = firstGreenS;
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
    // 실험 옵트인: BENCH_ADVISOR=1 이면 벤치 셀에만 advisor 를 켠다(라이브 config 는 불변).
    // BENCH_ADVISOR=<모델id> 면 advisor.model 도 지정 — 예: omlx/…-5bit:nothink 는 코더와 같은
    // 물리 모델의 프로파일이라 추가 상주 0 으로 35B 어드바이저가 된다(사용자 아이디어, 2026-08-27).
    // 이전 실측(2026-08-26)은 헤드리스 셀에서 advisor 무동작(aux 호출 0)이었다 — 재검증용 스위치.
    const adv = process.env.BENCH_ADVISOR;
    // 역할 키 정정(2026-08-28, 사용자 제공 문서): 어드바이저 모델은 modelRoles.advisor 로
    // 지정한다 — 과거 4중 무동작 프로브는 advisor.model 키를 쓴 탓일 수 있다. 두 형식과
    // --advisor 플래그를 모두 태워 재검증한다.
    const advisorRole = adv && adv !== "1" ? `  advisor: ${adv}\n` : "";
    const advisor = adv ? `advisor:\n  enabled: true\n  immuneTurns: 3\n${adv !== "1" ? `  model: ${adv}\n` : ""}` : "";
    // 실험 옵트인: BENCH_THINKING_BUDGET=<n> 이면 코더의 extraBody thinking_budget 을
    // 오버레이로 덮는다(라이브 config 불변). models.yml 실측 주석 참고: thinking_budget 은
    // 3.6 에서 실제로 먹는 유일한 thinking 제어(64→3000 비례 반응). 오버레이 딥머지가
    // 안 먹으면 셀의 thinking 비중이 5120 대역 그대로일 것 — 세션에서 자가 진단 가능.
    const tb = process.env.BENCH_THINKING_BUDGET;
    // BENCH_MAX_TOKENS=<n>: 출력 상한 축(사용자 제안 2026-08-28) — 한 번도 안 움직인 변수.
    // 하한 리스크: 절단(finish_reason=length)이 파일 쓰기·reasoning 분리를 깨뜬 실측 전례
    // 가 있어, 절단 발생은 세션에서 가드 지표로 같이 확인할 것.
    const mt = process.env.BENCH_MAX_TOKENS;
    const ov: string[] = [];
    if (tb) ov.push(`        compat:\n          extraBody:\n            thinking_budget: ${tb}`);
    if (mt) ov.push(`        maxTokens: ${mt}`);
    const budget = ov.length ? `providers:\n  omlx:\n    modelOverrides:\n      "${model.replace(/^omlx\//, "")}":\n${ov.join("\n")}\n` : "";
    writeFileSync(join(overlayDir, "overlay.yml"), `modelRoles:\n  tiny: ${AUX_MODEL}\n${advisorRole}${advisor}${budget}`);
    extra.push("--config", join(overlayDir, "overlay.yml"), "--smol", AUX_MODEL);
    // 실측(2026-08-27): config(advisor.enabled)만으로는 헤드리스에서 무동작(4중 0건),
    // --advisor CLI 플래그를 줘야 런타임이 깬다(플래그 프로브에서 세션 advisor 흔적 12건).
    if (adv) extra.push("--advisor");
  }
  // 실험 옵트인: BENCH_HOOK=<확장 .ts 경로> 면 그 훅을 로드한다(예: stuck-reset). 미설정이면 기존 동작.
  const benchHook = process.env.BENCH_HOOK;
  if (benchHook) extra.push("--hook", benchHook);

  // 어드바이저는 설정 파일 경로만 실동한다(사용자 실측 2026-08-28: config 의
  // advisor.enabled 토글이 동작, 오버레이 advisor 블록·과거 키는 무반응). 셀 단위로
  // sandbox/.omp/config.yml 에 블록을 주입하고 채점 전에 원문 복원한다. 비어드바이저
  // 셀은 enabled:false 를 강제해 사용자의 전역(홈) 토글이 암을 오염시키지 않게 한다.
  const projCfg = join(SANDBOX, ".omp", "config.yml");
  const projCfgOrig = readFileSync(projCfg, "utf-8");
  const advEnv = process.env.BENCH_ADVISOR;
  const advBlock = advEnv && advEnv !== "1"
    ? `\n# bench-advisor (runner-injected)\nmodelRoles:\n  advisor: ${advEnv}\nadvisor:\n  enabled: true\n  immuneTurns: 3\n  syncBacklog: "off"\n`
    : `\n# bench-advisor off (runner-injected)\nadvisor:\n  enabled: false\n`;
  writeFileSync(projCfg, projCfgOrig + advBlock);

  const started = Date.now();
  // 2단계 분해(BENCH_PHASE2=1, 2026-08-28 설계): 구현 세션 → fresh-context 마감 세션.
  // 중간 revert 없음 — 종반 분산이 긴 컨텍스트와 상관이라는 부검 관찰의 구조 실험.
  const phase2 = process.env.BENCH_PHASE2 === "1";
  const p1cap = Number(process.env.BENCH_P1_TIMEOUT ?? 1500);
  const p2cap = Number(process.env.BENCH_P2_TIMEOUT ?? 1500);
  const FINISH_PROMPT = `The \`notice\` CRUD domain has been partially implemented in this repository by a previous session. Your job is to FINISH it to the gate:

1. Run \`make verify\` from the sandbox root first — treat its output as the todo list.
2. Fix everything it reports: wiring (alembic/env.py, app/main.py, app/dependencies/services.py), the migration, the request file, and the sibling-parity tests at 100% coverage (backend/tests/{api,repositories,services}/test_notice.py, plus the expected-http-files list in backend/tests/core/test_seed_api_actor.py).
3. Do not refactor working code; add what is missing, fix what is red.
4. Finish only when a fresh full \`make verify\` passes end-to-end.`;
  const sessionPlans: Array<[string, number]> = phase2
    ? [[task.prompt(spec), p1cap], [FINISH_PROMPT, p2cap]]
    : [[task.prompt(spec), opts.timeoutS]];
  let timedOut = false;
  const phaseWalls: number[] = [];
  for (const [sessionPrompt, cap] of sessionPlans) {
    const pStart = Date.now();
    const child = spawn("omp", ["-p", sessionPrompt, "--model", model, ...extra], { cwd: SANDBOX, stdio: "ignore", detached: true });
    const killGroup = (signal: string): void => { spawnSync("kill", [`-${signal}`, `-${child.pid}`], { encoding: "utf-8" }); };
    await new Promise<void>((resolveP) => {
      const timer = setTimeout(() => {
        timedOut = true;
        killGroup("TERM");
        setTimeout(() => { killGroup("KILL"); resolveP(); }, 60_000);
      }, cap * 1000);
      child.on("exit", () => { clearTimeout(timer); resolveP(); });
    });
    phaseWalls.push(Math.round((Date.now() - pStart) / 1000));
  }
  const wall = Math.round((Date.now() - started) / 1000);
  writeFileSync(projCfg, projCfgOrig); // 채점 전에 프로젝트 설정 원문 복원

  const res = residency(model);
  if (overlayDir) rmSync(overlayDir, { recursive: true, force: true });
  if (res && res.ok === false) console.error(`  !! residency: loaded_count=${res.loaded_count} (예상 코더+4B aux) — 재시작/역할 고정 확인 후 재실행`);
  const row: Record<string, unknown> = {
    model, task: taskName, mode: task.mode, wall_s: wall, timed_out: timedOut,
    bundle: process.env.BENCH_BUNDLE ?? null, attempt: Number(process.env.BENCH_ATTEMPT ?? 1),
    ...(phaseWalls.length > 1 ? { phase_walls: phaseWalls } : {}),
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

  // KST(UTC+9) 기준 날짜 — 파일명이 사용자 로컬 날짜와 맞게(본문 시각도 KST).
  const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
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
