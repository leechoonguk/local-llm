/**
 * check-harness-proofs — sandbox 하네스(discipline 신호 · additive 가드)의 합성 프루프를 실제로 돌린다.
 *
 * 규칙: .claude/rules/harness-proofs.md
 *  - `.claude/skills/llm-bench/proofs/*.proof.mjs` 가 하나 이상 있고, 각각 FAIL 0 으로 끝난다
 *  - 프루프는 합성 이벤트만 쓴다(GPU·서버 없음). 픽스처는 os.tmpdir() 아래에만 만든다
 *
 * 다른 검사와 달리 파일을 읽는 데서 그치지 않고 프루프를 실행한다 — 신호는 "존재"가 아니라
 * "경계까지 맞는가"가 계약이고, 그건 돌려봐야만 안다(실측: 오발 하나가 벤치 셀을 통째로 날렸다).
 * 네트워크·서버는 만지지 않는다.
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { type Check, type Issue, isMain, runCli } from "./lib/harness.ts";

const DIR = ".claude/skills/llm-bench/proofs";

export function run(root: string): Issue[] {
  const issues: Issue[] = [];
  const dir = join(root, DIR);
  if (!existsSync(dir)) return [`${DIR} 가 없다 — 하네스 프루프는 레포 자산이다(세션 스크래치 금지)`];
  const files = readdirSync(dir).filter((f) => f.endsWith(".proof.mjs")).sort();
  if (files.length === 0) issues.push(`${DIR} 에 *.proof.mjs 가 없다`);
  for (const f of files) {
    const r = spawnSync("node", ["--experimental-strip-types", join(dir, f)], { encoding: "utf-8", cwd: root, timeout: 120_000 });
    const out = `${r.stdout ?? ""}${r.stderr ?? ""}`;
    const pass = (out.match(/^PASS/gm) ?? []).length;
    const fail = (out.match(/^FAIL/gm) ?? []).length;
    if (r.status !== 0 || fail > 0) {
      const first = (out.match(/^FAIL.*$/m) ?? ["(출력 없음)"])[0];
      issues.push(`${DIR}/${f}: ${fail} FAIL / ${pass} PASS — ${first.slice(0, 120)}`);
    } else if (pass === 0) {
      issues.push(`${DIR}/${f}: PASS 가 0 이다 — 프루프가 실행되지 않았다(경로·import 확인)`);
    }
  }
  return issues;
}

export const check: Check = { name: "harness-proofs", run };
if (isMain(import.meta.url)) runCli(check);
