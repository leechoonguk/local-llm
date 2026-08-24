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

async function restartOmlx(): Promise<void> {
  sh("brew", ["services", "restart", "jundot/omlx/omlx"], WORKSPACE, 120_000);
  for (let i = 0; i < 60; i++) {
    const r = sh("curl", ["-s", "-o", "/dev/null", "-w", "%{http_code}", `${OMLX_URL}/v1/models`], WORKSPACE, 5_000);
    if (r.out.trim() === "200") return;
    await new Promise((res) => setTimeout(res, 2_000));
  }
  throw new Error("oMLX did not come back on :9090 within 120s");
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

  if (model.startsWith("omlx/") && opts.restartOmlx) await restartOmlx();
  if (model.startsWith("ollama/")) unloadOllama();

  const started = Date.now();
  const child = spawn("omp", ["-p", task.prompt(spec), "--model", model], { cwd: SANDBOX, stdio: "ignore", detached: true });
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

  const ps = model.startsWith("ollama/") ? sh("ollama", ["ps"], WORKSPACE).out.trim().split("\n") : [];
  const row: Record<string, unknown> = {
    model, task: taskName, mode: task.mode, wall_s: wall, timed_out: timedOut,
    ps: ps.length > 1 ? ps[ps.length - 1] : "",
    ...grade(task, models, snapshot),
    ...sessionMetrics(newestSessionAfter(started)),
  };
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
