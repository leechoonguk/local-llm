/**
 * check-omp-models — omp/models.yml, omp/config.fragment.yml 이 서빙 쪽 설정과 맞는지.
 *
 * 규칙: .claude/rules/omp-models.md
 *  - provider `ollama`(openai-responses) 와 `ollama-nothink`(openai-completions + reasoning_effort: none)
 *    는 둘 다 있어야 하고 합치지 않는다
 *  - Modelfile.<name> 마다 `ollama-nothink.models` 에 `<name>:latest` 가 있고 contextWindow == num_ctx,
 *    maxTokens <= num_predict. `ollama.modelOverrides` 에 있으면 contextWindow == num_ctx, maxTokens == num_predict
 *  - `<name>:latest` 를 쓰는 항목은 Modelfile.<name> 이 있어야 한다. compactionModel 은 실재하는 provider/id
 *  - `omlx` provider 의 id 는 omlx/model_profiles.json 의 `<model>:<profile>`(expose_as_model) 또는
 *    model_settings.json 의 모델이고 contextWindow/maxTokens 가 그쪽 max_context_window/max_tokens 와 같다
 *  - omlx 에서 compat.extraBody 를 싣는 id 는 `api: openai-completions` 여야 한다(openai-responses 는 미병합, 실측)
 *  - config.fragment.yml 의 modelRoles 값은 models.yml 에 실재하는 `provider/id`
 */
import { type Check, type Issue, get, isMain, parseYaml, read, runCli } from "./lib/harness.ts";
import { modelfiles } from "./check-ollama-modelfile.ts";

type Rec = Record<string, unknown>;

export function loadModelsYml(root: string): { providers: Rec; issues: Issue[] } {
  const text = read(root, "omp/models.yml");
  if (text === null) return { providers: {}, issues: ["omp/models.yml 가 없다"] };
  try {
    const y = parseYaml(text) as Rec;
    const providers = (y?.providers ?? {}) as Rec;
    return { providers, issues: [] };
  } catch (e) { return { providers: {}, issues: [`omp/models.yml: 파싱 실패 — ${(e as Error).message}`] }; }
}

/** provider 안의 모든 모델 id → 항목(맵). models 리스트와 modelOverrides 를 합친다. */
export function providerModels(p: Rec): Map<string, Rec> {
  const out = new Map<string, Rec>();
  for (const m of (p.models as Rec[] | undefined) ?? []) if (m && typeof m.id === "string") out.set(m.id, m);
  for (const [id, o] of Object.entries((p.modelOverrides as Rec | undefined) ?? {})) out.set(id, { ...(out.get(id) ?? {}), ...(o as Rec) });
  return out;
}

export function run(root: string): Issue[] {
  const { providers, issues } = loadModelsYml(root);
  if (issues.length) return issues;
  const F = "omp/models.yml";

  // --- 두 Ollama provider ---
  const ol = providers.ollama as Rec | undefined, nt = providers["ollama-nothink"] as Rec | undefined;
  if (!ol) issues.push(`${F}: provider 'ollama' 가 없다`);
  if (!nt) issues.push(`${F}: provider 'ollama-nothink' 가 없다`);
  if (ol && ol.api !== "openai-responses") issues.push(`${F}: ollama.api 는 openai-responses 여야 한다(${String(ol.api)})`);
  if (nt) {
    if (nt.api !== "openai-completions") issues.push(`${F}: ollama-nothink.api 는 openai-completions 여야 한다(${String(nt.api)})`);
    if (get(nt, "compat.extraBody.reasoning_effort") !== "none") issues.push(`${F}: ollama-nothink.compat.extraBody.reasoning_effort: none 이 없다`);
  }

  const mfs = modelfiles(root);
  const olModels = ol ? providerModels(ol) : new Map<string, Rec>();
  const ntModels = nt ? providerModels(nt) : new Map<string, Rec>();
  for (const [name, mf] of mfs) {
    const id = `${name}:latest`;
    const ctx = Number(mf.params.num_ctx), pred = Number(mf.params.num_predict);
    const n = ntModels.get(id);
    if (!n) issues.push(`${F}: ollama-nothink.models 에 ${id} 가 없다(ollama/Modelfile.${name})`);
    else {
      if (n.contextWindow !== ctx) issues.push(`${F}: ollama-nothink ${id}.contextWindow(${String(n.contextWindow)}) != Modelfile num_ctx(${ctx})`);
      if (typeof n.maxTokens !== "number" || n.maxTokens > pred) issues.push(`${F}: ollama-nothink ${id}.maxTokens(${String(n.maxTokens)}) > Modelfile num_predict(${pred})`);
    }
    const o = olModels.get(id);
    if (o) {
      if (o.contextWindow !== ctx) issues.push(`${F}: ollama ${id}.contextWindow(${String(o.contextWindow)}) != Modelfile num_ctx(${ctx})`);
      if (o.maxTokens !== pred) issues.push(`${F}: ollama ${id}.maxTokens(${String(o.maxTokens)}) != Modelfile num_predict(${pred})`);
    }
  }
  for (const [prov, models] of [["ollama", olModels], ["ollama-nothink", ntModels]] as const) {
    for (const id of models.keys()) {
      const m = id.match(/^(.+):latest$/);
      if (!m || !mfs.has(m[1])) issues.push(`${F}: ${prov} 의 ${id} 에 대응하는 ollama/Modelfile 이 없다`);
    }
  }

  // --- compactionModel / modelRoles 참조 실재 ---
  const exists = (ref: string): boolean => {
    const i = ref.indexOf("/");
    if (i < 0) return false;
    const p = providers[ref.slice(0, i)] as Rec | undefined;
    return !!p && providerModels(p).has(ref.slice(i + 1));
  };
  for (const [prov, p] of Object.entries(providers)) {
    for (const [id, m] of providerModels(p as Rec)) {
      const c = m.compactionModel;
      if (typeof c === "string" && !exists(c)) issues.push(`${F}: ${prov}/${id}.compactionModel → ${c} 가 없다`);
    }
  }

  // --- omlx provider ↔ omlx/*.json ---
  const om = providers.omlx as Rec | undefined;
  if (om) {
    const settings = safeJson(read(root, "omlx/model_settings.json"));
    const profiles = safeJson(read(root, "omlx/model_profiles.json"));
    const sModels = (settings?.models ?? {}) as Rec;
    const pModels = (profiles?.profiles ?? {}) as Rec;
    if (!settings || !profiles) issues.push(`${F}: omlx provider 가 있는데 omlx/model_settings.json·model_profiles.json 을 읽을 수 없다`);
    else for (const [id, m] of providerModels(om)) {
      const [model, profile] = id.split(":");
      let target: Rec | undefined;
      if (profile) {
        const pr = (pModels[model] as Rec | undefined)?.[profile] as Rec | undefined;
        if (!pr) { issues.push(`${F}: omlx/${id} — model_profiles.json 에 ${model} 의 프로파일 ${profile} 이 없다`); continue; }
        if (pr.expose_as_model !== true) issues.push(`${F}: omlx/${id} — 프로파일 expose_as_model 이 true 가 아니다`);
        target = pr.settings as Rec;
      } else {
        target = sModels[model] as Rec | undefined;
        if (!target) { issues.push(`${F}: omlx/${id} — model_settings.json 에 ${model} 이 없다`); continue; }
      }
      if (m.contextWindow !== target.max_context_window) issues.push(`${F}: omlx/${id}.contextWindow(${String(m.contextWindow)}) != oMLX max_context_window(${String(target.max_context_window)})`);
      if (m.maxTokens !== target.max_tokens) issues.push(`${F}: omlx/${id}.maxTokens(${String(m.maxTokens)}) != oMLX max_tokens(${String(target.max_tokens)})`);
      if (get(m, "compat.extraBody") && m.api !== "openai-completions") issues.push(`${F}: omlx/${id} 가 compat.extraBody 를 싣는데 api: openai-completions 가 아니다(openai-responses 는 extraBody 미병합)`);
    }
  }

  // --- config.fragment.yml ---
  const frag = read(root, "omp/config.fragment.yml");
  if (frag === null) issues.push("omp/config.fragment.yml 가 없다");
  else {
    try {
      const y = parseYaml(frag) as Rec;
      const roles = (y.modelRoles ?? {}) as Rec;
      if (typeof roles.default !== "string") issues.push("omp/config.fragment.yml: modelRoles.default 가 없다");
      for (const [role, ref] of Object.entries(roles)) {
        if (typeof ref === "string" && !exists(ref)) issues.push(`omp/config.fragment.yml: modelRoles.${role} → ${ref} 가 models.yml 에 없다`);
      }
      if (!("defaultThinkingLevel" in y)) issues.push("omp/config.fragment.yml: defaultThinkingLevel 이 없다");
    } catch (e) { issues.push(`omp/config.fragment.yml: 파싱 실패 — ${(e as Error).message}`); }
  }
  return issues;
}

function safeJson(text: string | null): Rec | null {
  if (text === null) return null;
  try { return JSON.parse(text) as Rec; } catch { return null; }
}

export const check: Check = { name: "check-omp-models", run };
if (isMain(import.meta.url)) runCli(check);
