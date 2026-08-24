/**
 * check-ollama-modelfile — ollama/Modelfile.* 와 ollama/install.sh 의 정합성.
 *
 * 규칙: .claude/rules/ollama-modelfile.md
 *  - 파일명 `Modelfile.<name>`, 헤더 주석에 `Create: ollama create <name> -f ollama/Modelfile.<name>`
 *  - FROM 1개. PARAMETER num_ctx / num_predict 는 정수이고 num_predict < num_ctx
 *  - 샘플링(temperature/top_p/top_k)은 모델 카드 권장값 — 주석에 출처("권장"/"출처"/모델 카드) 표기
 *  - install.sh 가 `ollama create <name> -f "$HERE/Modelfile.<name>"` 로 만든다(옵션 블록이어도 됨).
 *    Ollama 태그를 FROM 으로 쓰면 install.sh 가 그 태그를 `ollama pull` 한다
 */
import { type Check, type Issue, isMain, listFiles, parseModelfile, read, runCli } from "./lib/harness.ts";

export function modelfiles(root: string): Map<string, ReturnType<typeof parseModelfile>> {
  const out = new Map<string, ReturnType<typeof parseModelfile>>();
  for (const f of listFiles(root, "ollama")) {
    const m = f.match(/^Modelfile\.(.+)$/);
    if (m) out.set(m[1], parseModelfile(m[1], read(root, `ollama/${f}`) ?? ""));
  }
  return out;
}

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const install = read(root, "ollama/install.sh") ?? "";
  if (install === "") issues.push("ollama/install.sh 가 없다");
  const mfs = modelfiles(root);
  if (mfs.size === 0) issues.push("ollama/Modelfile.* 가 하나도 없다");

  for (const [name, mf] of mfs) {
    const rel = `ollama/Modelfile.${name}`;
    if (!/^[a-z0-9][a-z0-9.-]*$/.test(name)) issues.push(`${rel}: 파생 이름은 소문자·숫자·점·하이픈만`);
    const create = `ollama create ${name} -f ollama/Modelfile.${name}`;
    if (!mf.header.some((h) => h.includes(create))) issues.push(`${rel}: 헤더 주석에 "Create: ${create}" 가 없다`);
    if (!mf.from) issues.push(`${rel}: FROM 이 없다`);
    const ctx = Number(mf.params.num_ctx), pred = Number(mf.params.num_predict);
    if (!Number.isInteger(ctx) || ctx <= 0) issues.push(`${rel}: PARAMETER num_ctx 가 정수가 아니다(${mf.params.num_ctx ?? "없음"})`);
    if (!Number.isInteger(pred) || pred <= 0) issues.push(`${rel}: PARAMETER num_predict 가 정수가 아니다(${mf.params.num_predict ?? "없음"})`);
    if (Number.isInteger(ctx) && Number.isInteger(pred) && pred >= ctx) issues.push(`${rel}: num_predict(${pred}) 가 num_ctx(${ctx}) 이상이다 — 프롬프트 몫이 남지 않는다`);
    for (const p of ["temperature", "top_p", "top_k"]) if (!(p in mf.params)) issues.push(`${rel}: PARAMETER ${p} 가 없다`);
    const comments = mf.header.join("\n");
    if (!/권장|출처|모델 카드|model card|official|recommended/i.test(comments)) issues.push(`${rel}: 샘플링 값의 출처(권장/출처/모델 카드) 주석이 없다`);
    if (install !== "") {
      if (!install.includes(`ollama create ${name} -f "$HERE/Modelfile.${name}"`)) issues.push(`ollama/install.sh: 'ollama create ${name} -f "$HERE/Modelfile.${name}"' 가 없다`);
      if (mf.from && !mfs.has(mf.from) && !install.includes(`ollama pull ${mf.from}`)) issues.push(`ollama/install.sh: 'ollama pull ${mf.from}' 가 없다(${rel} 의 FROM)`);
    }
  }
  // install.sh 가 만드는 이름은 전부 Modelfile 이 있어야 한다.
  for (const m of install.matchAll(/ollama create (\S+) -f "\$HERE\/Modelfile\.([^"]+)"/g)) {
    if (m[1] !== m[2]) issues.push(`ollama/install.sh: 'ollama create ${m[1]}' 이 Modelfile.${m[2]} 를 가리킨다 — 이름이 다르다`);
    if (!mfs.has(m[2])) issues.push(`ollama/install.sh: Modelfile.${m[2]} 가 없다`);
  }
  if (install !== "" && !/launchctl bootstrap/.test(install)) issues.push("ollama/install.sh: LaunchAgent 부트스트랩이 없다(brew services 금지)");
  if (/brew services (start|restart) ollama/.test(install)) issues.push("ollama/install.sh: 'brew services start ollama' 금지 — LaunchAgent 만 쓴다");
  return issues;
}

export const check: Check = { name: "check-ollama-modelfile", run };
if (isMain(import.meta.url)) runCli(check);
