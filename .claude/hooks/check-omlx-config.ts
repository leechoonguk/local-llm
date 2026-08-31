/**
 * check-omlx-config — omlx/model_settings.json, model_profiles.json, install.sh 의 정합성.
 *
 * 규칙: .claude/rules/omlx-config.md
 *  - 두 JSON 모두 version 1. 설정마다 max_context_window > max_tokens(정수)
 *  - Qwen 계열은 enable_thinking 이면 reasoning_parser: "qwen"(없으면 CoT 가 content 에 섞임).
 *    다른 계열은 서버가 계열별 출력 파서를 스스로 붙이므로(로그 `Output parser detected: <family>`)
 *    파서 이름을 요구하지 않는다 — 값이 있다면 비어 있지 않은 문자열이어야 한다
 *  - MTP 를 죽이는 값 금지: repetition_penalty != 1, presence_penalty != 0, guided_grammar
 *  - vlm_mtp_enabled 면 vlm_mtp_draft_model 필수. is_default 는 정확히 1개. active_profile_name 은 실재
 *  - 프로파일: key == name == api_name. 같은 모델의 프로파일들은 창·MTP 설정이 같아야(엔진 시그니처 동일 → 같은 슬롯)
 *    `nothink` 는 enable_thinking false, `mtp` 는 vlm_mtp_enabled true
 *  - install.sh: 모델·드래프터마다 `$HF download …` 또는 앱 스토어 관리 주석에 이름 명기, memory_guard_tier 'safe', 포트 9090
 */
import { type Check, type Issue, isMain, read, runCli } from "./lib/harness.ts";

type Rec = Record<string, unknown>;
const NEUTRAL: Array<[string, unknown]> = [["repetition_penalty", 1], ["presence_penalty", 0]];

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const S = "omlx/model_settings.json", P = "omlx/model_profiles.json", I = "omlx/install.sh";
  const settings = parse(root, S, issues), profiles = parse(root, P, issues);
  const install = read(root, I);
  if (install === null) issues.push(`${I} 가 없다`);
  if (!settings || !profiles) return issues;

  const models = (settings.models ?? {}) as Rec;
  const profs = (profiles.profiles ?? {}) as Rec;
  if (settings.version !== 1) issues.push(`${S}: version 1 이 아니다`);
  if (profiles.version !== 1) issues.push(`${P}: version 1 이 아니다`);

  const hf = new Set<string>();
  for (const m of (install ?? "").matchAll(/\$HF download (\S+)/g)) hf.add(m[1]);
  const needDownload = (name: string, why: string) => {
    const repo = name.replace("--", "/");
    // 2026-08-28 전면 포팅: 모델은 oMLX 앱 스토어(~/.omlx/models)로 관리한다 —
    // $HF download 줄 또는 앱 관리 주석에 짧은 이름이 명기돼 있으면 통과.
    if (install !== null && !hf.has(repo) && !install.includes(name)) {
      issues.push(`${I}: '$HF download ${repo}' 도, 앱 스토어 관리 주석의 '${name}' 도 없다(${why})`);
    }
  };

  let defaults = 0;
  for (const [name, raw] of Object.entries(models)) {
    const s = raw as Rec;
    issues.push(...checkSettings(`${S} ${name}`, s));
    if (s.is_default === true) defaults++;
    needDownload(name, "model_settings");
    if (typeof s.vlm_mtp_draft_model === "string") needDownload(s.vlm_mtp_draft_model, `${name} 드래프터`);
    if (typeof s.active_profile_name === "string") {
      const pr = profs[name] as Rec | undefined;
      if (!pr || !(s.active_profile_name in pr)) issues.push(`${S} ${name}: active_profile_name '${s.active_profile_name}' 프로파일이 없다`);
    }
  }
  if (defaults !== 1) issues.push(`${S}: is_default: true 는 정확히 1개여야 한다(${defaults})`);

  for (const [model, raw] of Object.entries(profs)) {
    const group = raw as Rec;
    if (!(model in models)) issues.push(`${P} ${model}: model_settings.json 에 없는 모델이다`);
    const sig = new Map<string, string>();
    for (const [key, praw] of Object.entries(group)) {
      const p = praw as Rec, tag = `${P} ${model}:${key}`;
      for (const f of ["name", "api_name"]) if (p[f] !== key) issues.push(`${tag}: ${f}(${String(p[f])}) 가 key 와 다르다`);
      const st = (p.settings ?? {}) as Rec;
      issues.push(...checkSettings(tag, st));
      if (key === "nothink" && st.enable_thinking !== false) issues.push(`${tag}: nothink 프로파일은 enable_thinking: false`);
      if (key === "mtp" && st.vlm_mtp_enabled !== true) issues.push(`${tag}: mtp 프로파일은 vlm_mtp_enabled: true`);
      if (typeof st.vlm_mtp_draft_model === "string") needDownload(st.vlm_mtp_draft_model, `${model}:${key} 드래프터`);
      sig.set(key, JSON.stringify([st.max_context_window, st.vlm_mtp_enabled ?? false, st.vlm_mtp_draft_model ?? null]));
    }
    const sigs = new Set(sig.values());
    if (sigs.size > 1) issues.push(`${P} ${model}: 프로파일 간 창/MTP 설정이 다르다(${[...sig].map(([k, v]) => `${k}=${v}`).join(", ")}) — 같은 슬롯을 못 쓴다`);
  }

  if (install !== null) {
    if (!/memory_guard_tier'\]\s*=\s*'safe'|"memory_guard_tier"\s*:\s*"safe"/.test(install)) issues.push(`${I}: memory_guard_tier 를 'safe' 로 강제하지 않는다`);
    if (!/\['port'\]\s*=\s*9090/.test(install)) issues.push(`${I}: 포트 9090 설정이 없다`);
    for (const f of ["model_settings.json", "model_profiles.json"]) if (!install.includes(`cp ${f} ~/.omlx/${f}`)) issues.push(`${I}: 'cp ${f} ~/.omlx/${f}' 가 없다`);
  }
  return issues;
}

function checkSettings(tag: string, s: Rec): Issue[] {
  const out: Issue[] = [];
  const ctx = s.max_context_window, mt = s.max_tokens;
  if (!Number.isInteger(ctx)) out.push(`${tag}: max_context_window 가 정수가 아니다`);
  if (!Number.isInteger(mt)) out.push(`${tag}: max_tokens 가 정수가 아니다`);
  if (Number.isInteger(ctx) && Number.isInteger(mt) && (mt as number) >= (ctx as number)) out.push(`${tag}: max_tokens >= max_context_window`);
  // 파서 요구는 계열별이다. Qwen 은 xgrammar 의 `qwen` 구조 태그가 있어야 thinking 이 분리되지만,
  // Gemma 4 는 서버가 gemma4 출력 파서를 자동 감지하고(로그로 확인) xgrammar 0.2.3 은 `gemma_4`
  // 태그 등록을 주석 처리해 뒀다 — 이름을 넣을 곳이 없다. 실측으로 reasoning_content 는 분리된다.
  const qwenFamily = /^Qwen/i.test(tag.split(/[ :]/)[1] ?? tag);
  if (s.enable_thinking === true && qwenFamily && s.reasoning_parser !== "qwen") out.push(`${tag}: Qwen 계열이 enable_thinking 인데 reasoning_parser: "qwen" 이 없다`);
  if ("reasoning_parser" in s && s.reasoning_parser !== null && typeof s.reasoning_parser !== "string") out.push(`${tag}: reasoning_parser 는 문자열이어야 한다`);
  for (const [k, v] of NEUTRAL) if (k in s && s[k] !== v) out.push(`${tag}: ${k}=${String(s[k])} — 비중립값은 MTP 를 끈다`);
  if ("guided_grammar" in s) out.push(`${tag}: guided_grammar 는 MTP 를 끈다`);
  if (s.vlm_mtp_enabled === true && typeof s.vlm_mtp_draft_model !== "string") out.push(`${tag}: vlm_mtp_enabled 인데 vlm_mtp_draft_model 이 없다`);
  return out;
}

function parse(root: string, rel: string, issues: Issue[]): Rec | null {
  const t = read(root, rel);
  if (t === null) { issues.push(`${rel} 가 없다`); return null; }
  try { return JSON.parse(t) as Rec; } catch (e) { issues.push(`${rel}: JSON 파싱 실패 — ${(e as Error).message}`); return null; }
}

export const check: Check = { name: "check-omlx-config", run };
if (isMain(import.meta.url)) runCli(check);
