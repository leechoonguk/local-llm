/**
 * check-live-sync — 레포의 설정(ollama/, omlx/, omp/)이 이 호스트의 라이브 시스템에 반영돼 있는지.
 *
 * 규칙: .claude/rules/live-sync.md
 *  - omp: `omp config path`(없으면 ~/.omp/agent) 의 models.yml 이 omp/models.yml 과 바이트 동일,
 *    config.yml 이 config.fragment.yml 의 modelRoles(default/tiny)·defaultThinkingLevel 을 담는다
 *  - oMLX: ~/.omlx/model_settings.json·model_profiles.json 이 레포와 JSON 동일, settings.json 의 port /
 *    memory_guard_tier / hot_cache_max_size 가 install.sh 가 쓰는 값, 모델·드래프터가 HF 캐시에 있다
 *  - Ollama: LaunchAgent plist 설치 + 자리표시자 치환. 서버가 떠 있으면(127.0.0.1:11434, 2s)
 *    Modelfile 마다 모델이 있고 num_ctx/num_predict/샘플링이 Modelfile 과 같다. 서버가 없으면 그 부분은 건너뛴다
 *
 * 다른 검사와 달리 호스트 상태를 읽는다 — 설치돼 있지 않은 시스템은 이슈가 아니라 "skip" 으로 알린다
 * (48GB 맥, omp 미설치 호스트에서도 verify 가 깨지지 않도록). 네트워크는 루프백 한 곳뿐이다.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { type Check, type Issue, isMain, parseYaml, read, runCli } from "./lib/harness.ts";
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
    } catch { /* omp-models 가 보고한다 */ }
  }
  return issues;
}

// --- oMLX ------------------------------------------------------------------------
function checkOmlx(root: string): Issue[] {
  const issues: Issue[] = [];
  const dir = join(homedir(), ".omlx");
  if (!existsSync(dir)) { notes.push(`oMLX: ${dir} 없음 — 건너뜀(oMLX 미설치)`); return issues; }
  if (!existsSync("/Applications/oMLX.app")) issues.push("oMLX: /Applications/oMLX.app 이 없다 — 서버는 GUI 앱이 관리한다(DMG: github.com/jundot/omlx/releases)");
  for (const f of ["model_settings.json", "model_profiles.json"]) {
    const src = jsonOf(read(root, `omlx/${f}`)), live = existsSync(join(dir, f)) ? jsonOf(readFileSync(join(dir, f), "utf-8")) : null;
    if (live === null) issues.push(`oMLX: ${dir}/${f} 이 없다 — cp omlx/${f} ${dir}/${f}`);
    else if (canon(src) !== canon(live)) issues.push(`oMLX: ${dir}/${f} 이 omlx/${f} 과 다르다 — cp omlx/${f} ${dir}/${f} 후 omlx restart (메뉴바 앱)`);
  }
  const settings = existsSync(join(dir, "settings.json")) ? jsonOf(readFileSync(join(dir, "settings.json"), "utf-8")) : null;
  const install = read(root, "omlx/install.sh") ?? "";
  if (settings === null) issues.push(`oMLX: ${dir}/settings.json 이 없다`);
  else {
    const want: Array<[string, string, unknown]> = [
      ["server", "port", Number(install.match(/\['port'\]\s*=\s*(\d+)/)?.[1] ?? 9090)],
      ["memory", "memory_guard_tier", install.match(/\['memory_guard_tier'\]\s*=\s*'([^']+)'/)?.[1] ?? "safe"],
      ["cache", "hot_cache_max_size", install.match(/\['hot_cache_max_size'\]\s*=\s*'([^']+)'/)?.[1] ?? "4GB"],
    ];
    for (const [sec, key, val] of want) {
      const cur = ((settings[sec] ?? {}) as Rec)[key];
      if (cur !== val) issues.push(`oMLX: ${dir}/settings.json ${sec}.${key} = ${JSON.stringify(cur)}, install.sh 는 ${JSON.stringify(val)}`);
    }
  }
  const hub = join(homedir(), ".cache", "huggingface", "hub");
  const models = ((jsonOf(read(root, "omlx/model_settings.json"))?.models ?? {}) as Rec);
  for (const [name, raw] of Object.entries(models)) {
    for (const n of [name, (raw as Rec).vlm_mtp_draft_model].filter((x): x is string => typeof x === "string")) {
      if (!existsSync(join(hub, `models--${n}`))) issues.push(`oMLX: HF 캐시에 ${n} 이 없다 — 다운로드는 사용자가 omlx/install.sh 로 직접`);
    }
  }
  return issues;
}

// --- Ollama ----------------------------------------------------------------------
function checkOllama(root: string): Issue[] {
  const issues: Issue[] = [];
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
function canon(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canon).join(",")}]`;
  if (v && typeof v === "object") return `{${Object.keys(v as Rec).sort().map((k) => `${JSON.stringify(k)}:${canon((v as Rec)[k])}`).join(",")}}`;
  return JSON.stringify(v);
}
function jsonOf(t: string | null): Rec | null { if (t === null) return null; try { return JSON.parse(t) as Rec; } catch { return null; } }
function escapeRe(s: string): string { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

export const check: Check = { name: "check-live-sync", run, notes: () => notes };
if (isMain(import.meta.url)) runCli(check);
