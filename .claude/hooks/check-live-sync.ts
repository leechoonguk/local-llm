/**
 * check-live-sync — 레포의 설정(ollama/, omlx/, omp/)이 이 호스트의 라이브 시스템에 반영돼 있는지.
 *
 * 규칙: .claude/rules/live-sync.md
 *  - omp: `omp config path`(없으면 ~/.omp/agent) 의 models.yml 이 omp/models.yml 과 바이트 동일,
 *    config.yml 이 config.fragment.yml 의 modelRoles(default/tiny)·defaultThinkingLevel 을 담는다
 *  - oMLX: ~/.omlx/model_settings.json·model_profiles.json 이 레포가 선언한 키마다 같은 값(앱이 채운 기본값은 드리프트 아님), settings.json 의 port /
 *    memory_guard_tier / hot_cache_max_size 가 install.sh 가 쓰는 값, 모델·드래프터가 앱 스토어(~/.omlx/models)나 HF 캐시에 있다
 *  - Ollama: LaunchAgent plist 설치 + 자리표시자 치환. 서버가 떠 있으면(127.0.0.1:11434, 2s)
 *    Modelfile 마다 모델이 있고 num_ctx/num_predict/샘플링이 Modelfile 과 같다. 서버가 없으면 그 부분은 건너뛴다
 *
 * 다른 검사와 달리 호스트 상태를 읽는다 — 설치돼 있지 않은 시스템은 이슈가 아니라 "skip" 으로 알린다
 * (48GB 맥, omp 미설치 호스트에서도 verify 가 깨지지 않도록). 네트워크는 루프백 한 곳뿐이다.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { type Check, type Issue, isInstalled, isMain, parseYaml, read, runCli } from "./lib/harness.ts";
import { modelfiles } from "./check-ollama-modelfile.ts";

type Rec = Record<string, unknown>;
export const notes: string[] = [];

export function run(root: string): Issue[] {
  notes.length = 0;
  return [...checkOmp(root), ...checkOmlx(root), ...checkOllama(root)];
}

// --- omp -------------------------------------------------------------------------
function checkOmp(root: string): Issue[] {
  const issues: Issue[] = [];
  let dir = "";
  try { dir = execFileSync("omp", ["config", "path"], { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], timeout: 5000 }).trim().split("\n").pop() ?? ""; } catch { /* omp 없음 */ }
  if (!dir || !existsSync(dir)) dir = join(homedir(), ".omp", "agent");
  if (!existsSync(dir)) { notes.push(`omp: ${dir} 없음 — 건너뜀(oh-my-pi 미설치)`); return issues; }

  const src = read(root, "omp/models.yml"), live = existsSync(join(dir, "models.yml")) ? readFileSync(join(dir, "models.yml"), "utf-8") : null;
  if (live === null) issues.push(`omp: ${dir}/models.yml 이 없다 — cp omp/models.yml ${dir}/models.yml`);
  else if (src !== live) issues.push(`omp: ${dir}/models.yml 이 omp/models.yml 과 다르다 — cp omp/models.yml ${dir}/models.yml (다른 provider 가 있으면 병합)`);

  const cfg = existsSync(join(dir, "config.yml")) ? readFileSync(join(dir, "config.yml"), "utf-8") : null;
  const frag = read(root, "omp/config.fragment.yml");
  if (cfg === null) issues.push(`omp: ${dir}/config.yml 이 없다`);
  else if (frag !== null) {
    try {
      const y = parseYaml(frag) as Rec;
      for (const [role, ref] of Object.entries((y.modelRoles ?? {}) as Rec)) {
        const re = new RegExp(`^\\s*${role}:\\s*${escapeRe(String(ref))}\\s*$`, "m");
        if (!re.test(cfg)) {
          const cur = cfg.match(new RegExp(`^\\s*${role}:\\s*(.*)$`, "m"))?.[1] ?? "없음";
          issues.push(`omp: ${dir}/config.yml modelRoles.${role} = ${cur}, 레포는 ${String(ref)} — config.yml 의 그 줄만 손으로 맞출 것`);
        }
      }
      if ("defaultThinkingLevel" in y && !new RegExp(`^defaultThinkingLevel:\\s*${escapeRe(String(y.defaultThinkingLevel))}\\s*$`, "m").test(cfg)) {
        issues.push(`omp: ${dir}/config.yml defaultThinkingLevel 이 ${String(y.defaultThinkingLevel)} 이 아니다`);
      }
      // advisor.enabled 고정(2026-09-01 사용자 결정): omp 가 세션마다 advisor 블록을 다시
      // 만들어 값이 표류할 수 있다 — fragment 의 enabled 값(false)과 다르면 빨간불.
      const fragAdvisor = (y.advisor as Rec | undefined)?.enabled;
      if (fragAdvisor !== undefined) {
        const liveAdvisor = /^advisor:\s*$[\s\S]*?^\s+enabled:\s*(\S+)\s*$/m.exec(cfg)?.[1];
        if (liveAdvisor !== undefined && liveAdvisor !== String(fragAdvisor)) {
          issues.push(`omp: ${dir}/config.yml advisor.enabled = ${liveAdvisor}, 레포는 ${String(fragAdvisor)} — config.yml 의 그 줄만 손으로 맞출 것`);
        }
      }
    } catch { /* omp-models 가 보고한다 */ }
  }
  return issues;
}

// --- oMLX ------------------------------------------------------------------------
function checkOmlx(root: string): Issue[] {
  const issues: Issue[] = [];
  if (!isInstalled("omlx", "oMLX.app")) { notes.push("oMLX: 미설치(CLI·GUI 앱 모두 없음) — 건너뜀"); return issues; }
  const dir = join(homedir(), ".omlx");
  if (!existsSync(dir)) { notes.push(`oMLX: ${dir} 없음 — 건너뜀(설정 미설치)`); return issues; }
  for (const f of ["model_settings.json", "model_profiles.json"]) {
    const src = jsonOf(read(root, `omlx/${f}`)), live = existsSync(join(dir, f)) ? jsonOf(readFileSync(join(dir, f), "utf-8")) : null;
    if (live === null) issues.push(`oMLX: ${dir}/${f} 이 없다 — cp omlx/${f} ${dir}/${f}`);
    else {
      // 바이트/JSON 동일이 아니라 **부분집합** 으로 본다. oMLX 앱은 파일을 다시 쓸 때 자기 기본값
      // 수십 개(qwen35_ane_prefill_*, dflash_*, is_favorite …)를 채워 넣는다 — 그건 우리 설정이 아니라
      // 앱의 내부 기본값이고, 앱 버전이 오를 때마다 레포에 베껴 넣으면 드리프트 신호가 잡음이 된다.
      // 계약은 "레포가 선언한 키는 라이브에서 그 값이어야 한다" 이다(2026-08-30).
      for (const path of mismatches(src, live, "")) {
        issues.push(`oMLX: ${dir}/${f} 의 ${path} 가 omlx/${f} 와 다르다 — cp omlx/${f} ${dir}/${f} 후 bash omlx/ensure-app-server.sh --restart`);
      }
    }
  }
  const settings = existsSync(join(dir, "settings.json")) ? jsonOf(readFileSync(join(dir, "settings.json"), "utf-8")) : null;
  const install = read(root, "omlx/install.sh") ?? "";
  if (settings === null) issues.push(`oMLX: ${dir}/settings.json 이 없다`);
  else {
    const want: Array<[string, string, unknown]> = [
      ["server", "port", Number(install.match(/\['port'\]\s*=\s*(\d+)/)?.[1] ?? 9090)],
      ["memory", "memory_guard_tier", install.match(/\['memory_guard_tier'\]\s*=\s*'([^']+)'/)?.[1] ?? "safe"],
      // hot_cache 는 RAM 티어별(install.sh 와 같은 규칙: 64GB+ 8GB / 그 아래 4GB, 2026-08-28)
      ["cache", "hot_cache_max_size", hostRamGb() >= 60 ? "8GB" : "4GB"],
    ];
    for (const [sec, key, val] of want) {
      const cur = ((settings[sec] ?? {}) as Rec)[key];
      if (cur !== val) issues.push(`oMLX: ${dir}/settings.json ${sec}.${key} = ${JSON.stringify(cur)}, install.sh 는 ${JSON.stringify(val)}`);
    }
  }
  // GPU wired 캡 래퍼(2026-09-24): 레포 omlx/wired-limit.sh 의 root 사본이 /usr/local/sbin 에 있고 내용이 같아야 한다.
  // 값 자체는 서버가 떠 있을 때만 본다 — 관문(ensure-app-server.sh)이 기동 시 올리므로, 서버가 살아 있는데
  // 티어와 다르면 래퍼 미설치·sudoers 누락·관문 우회 중 하나다. (부팅 지속은 설계상 없다 — 캡은 재부팅에 리셋)
  const wlSrc = read(root, "omlx/wired-limit.sh"), wlBin = "/usr/local/sbin/omlx-wired-limit";
  if (wlSrc !== null) {
    if (!existsSync(wlBin)) issues.push(`oMLX: ${wlBin} 이 없다 — 래퍼 미설치. bash omlx/install.sh (sudo 1회) 로 설치한다`);
    else if (readFileSync(wlBin, "utf-8") !== wlSrc) issues.push(`oMLX: ${wlBin} 이 omlx/wired-limit.sh 와 다르다 — bash omlx/install.sh 로 갱신`);
    const tier = Number(shOut("bash", [join(root, "omlx/wired-limit.sh"), "tier"]) || 0);
    const cur = Number(shOut("sysctl", ["-n", "iogpu.wired_limit_mb"]) || 0);
    if (tier > 0 && cur !== tier && api("/v1/models") !== null)
      issues.push(`oMLX: 서버가 떠 있는데 iogpu.wired_limit_mb = ${cur}, 티어는 ${tier} — bash omlx/ensure-app-server.sh --restart (래퍼·sudoers 가 있어야 올라간다)`);
  }
  const hub = join(homedir(), ".cache", "huggingface", "hub");
  const models = ((jsonOf(read(root, "omlx/model_settings.json"))?.models ?? {}) as Rec);
  for (const [name, raw] of Object.entries(models)) {
    for (const n of [name, (raw as Rec).vlm_mtp_draft_model].filter((x): x is string => typeof x === "string")) {
      // 2026-08-28 전면 포팅: 모델 저장소는 oMLX 앱 스토어(~/.omlx/models/<org>/<name>)다.
      // HF 캐시(models--org--name)는 폐지했지만, 옛 배치도 유효로 인정한다(이식성).
      // 스토어는 org 디렉터리로 갈라진다(mlx-community, z-lab, …) — 전부 훑는다.
      // 예전엔 mlx-community 만 봐서 z-lab 의 DFlash 사이드카를 "없다"고 했다(2026-08-31).
      const storeRoot = join(homedir(), ".omlx", "models");
      const inStore = existsSync(storeRoot) && readdirSync(storeRoot).some((org) => existsSync(join(storeRoot, org, n)));
      const inHub = existsSync(join(hub, `models--mlx-community--${n}`)) || existsSync(join(hub, `models--${n}`));
      if (!inStore && !inHub) issues.push(`oMLX: 앱 스토어(~/.omlx/models)에도 HF 캐시에도 ${n} 이 없다 — oMLX 앱 또는 POST /admin/api/hf/download 로 받는다`);
    }
  }
  return issues;
}

function shOut(cmd: string, args: string[]): string {
  try { return execFileSync(cmd, args, { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] }).trim(); } catch { return ""; }
}

function hostRamGb(): number {
  try { return Math.round(Number(execFileSync("sysctl", ["-n", "hw.memsize"], { encoding: "utf-8" }).trim()) / 1024 ** 3); } catch { return 0; }
}

// --- Ollama ----------------------------------------------------------------------
function checkOllama(root: string): Issue[] {
  const issues: Issue[] = [];
  if (!isInstalled("ollama", "Ollama.app")) { notes.push("Ollama: 미설치(CLI·GUI 앱 모두 없음) — 건너뜀"); return issues; }
  const plist = join(homedir(), "Library", "LaunchAgents", "com.ollama.serve.plist");
  if (!existsSync(plist)) { notes.push("Ollama: LaunchAgent plist 없음 — 건너뜀(ollama/install.sh 미실행)"); return issues; }
  const p = readFileSync(plist, "utf-8");
  if (/__HOME__|__MAX_LOADED_MODELS__/.test(p)) issues.push(`Ollama: ${plist} 에 치환되지 않은 자리표시자가 있다 — ollama/install.sh 로 다시 설치`);
  if (!/OLLAMA_MAX_LOADED_MODELS/.test(p)) issues.push(`Ollama: ${plist} 에 OLLAMA_MAX_LOADED_MODELS 가 없다`);

  const mfs = modelfiles(root);
  const tags = api("/api/tags");
  if (tags === null) { notes.push("Ollama: 127.0.0.1:11434 응답 없음 — 모델 파라미터 비교 건너뜀(서버가 내려가 있음, oMLX 전환 후 정상)"); return issues; }
  const names = new Set(((tags.models ?? []) as Rec[]).map((m) => String(m.name)));
  for (const [name, mf] of mfs) {
    if (!names.has(`${name}:latest`)) { issues.push(`Ollama: 모델 ${name} 이 없다 — ollama create ${name} -f ollama/Modelfile.${name}`); continue; }
    const show = api("/api/show", { name: `${name}:latest` });
    const params = parseParams(String(show?.parameters ?? ""));
    for (const [k, v] of Object.entries(mf.params)) {
      if (params[k] === undefined) issues.push(`Ollama: ${name} 에 ${k} 가 없다(Modelfile ${v}) — ollama create ${name} -f ollama/Modelfile.${name}`);
      else if (Number(params[k]) !== Number(v) && params[k] !== v) issues.push(`Ollama: ${name} ${k} = ${params[k]}, Modelfile 은 ${v} — ollama create 로 다시 만들 것`);
    }
  }
  return issues;
}

function api(path: string, body?: object): Rec | null {
  try {
    const args = ["-s", "--max-time", "2", `http://127.0.0.1:11434${path}`];
    if (body) args.push("-X", "POST", "-d", JSON.stringify(body));
    const out = execFileSync("curl", args, { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] });
    return JSON.parse(out) as Rec;
  } catch { return null; }
}

/** `ollama show` 의 parameters 블록: `num_ctx   131072` 줄들. 같은 키가 여러 번(stop)이면 마지막 값. */
function parseParams(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const l of text.split("\n")) { const m = l.trim().match(/^(\S+)\s+"?([^"]*)"?$/); if (m) out[m[1]] = m[2]; }
  return out;
}

/** 키 순서 무관 비교용 정렬 직렬화 — oMLX 가 저장하며 키 순서를 바꾼다. */
/**
 * 레포(src)가 선언한 키만 라이브(live)와 비교해, 어긋난 키 경로를 돌려준다.
 * 라이브에만 있는 키는 앱 기본값이므로 보지 않는다.
 */
function mismatches(src: unknown, live: unknown, path: string): string[] {
  if (src === null || typeof src !== "object" || Array.isArray(src)) {
    return canon(src) === canon(live) ? [] : [path === "" ? "값" : path];
  }
  if (live === null || typeof live !== "object" || Array.isArray(live)) return [path === "" ? "값" : path];
  const out: string[] = [];
  for (const k of Object.keys(src as Rec)) {
    if (k === "created_at" || k === "updated_at") continue; // 앱이 파일을 쓸 때 찍는 도장 — 설정이 아니다
    if (!(k in (live as Rec))) { out.push(`${path}${path === "" ? "" : "."}${k} (라이브에 없음)`); continue; }
    out.push(...mismatches((src as Rec)[k], (live as Rec)[k], `${path}${path === "" ? "" : "."}${k}`));
  }
  return out;
}

function canon(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canon).join(",")}]`;
  if (v && typeof v === "object") return `{${Object.keys(v as Rec).sort().map((k) => `${JSON.stringify(k)}:${canon((v as Rec)[k])}`).join(",")}}`;
  return JSON.stringify(v);
}
function jsonOf(t: string | null): Rec | null { if (t === null) return null; try { return JSON.parse(t) as Rec; } catch { return null; } }
function escapeRe(s: string): string { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

export const check: Check = { name: "check-live-sync", run, notes: () => notes };
if (isMain(import.meta.url)) runCli(check);
