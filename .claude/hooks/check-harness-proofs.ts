/**
 * check-harness-proofs — sandbox 하네스(discipline 신호 · additive 가드)의 합성 프루프를 실제로 돌린다.
 *
 * 규칙: .claude/rules/harness-proofs.md
 *  - `.claude/skills/llm-bench/proofs/*.proof.mjs` 가 하나 이상 있고, 각각 FAIL 0 으로 끝난다
 *  - 프루프는 합성 이벤트만 쓴다(GPU·서버 없음). 픽스처는 os.tmpdir() 아래에만 만든다
 *  - `sandbox/.omp/hooks/pre/*.ts` 는 하나 이상의 프루프가 이름으로 부른다
 *
 * 다른 검사와 달리 파일을 읽는 데서 그치지 않고 프루프를 실행한다 — 신호는 "존재"가 아니라
 * "경계까지 맞는가"가 계약이고, 그건 돌려봐야만 안다(실측: 오발 하나가 벤치 셀을 통째로 날렸다).
 * 네트워크·서버는 만지지 않는다.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { type Check, type Issue, isMain, runCli } from "./lib/harness.ts";

const DIR = ".claude/skills/llm-bench/proofs";
const GUARDS = "sandbox/.omp/hooks/pre";

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
  issues.push(...guardsWithoutProof(root, dir, files));
  return issues;
}

/**
 * 가드마다 프루프가 하나는 그 파일을 **이름으로** 불러야 한다.
 *
 * 초록 프루프는 "이 가드가 옳다"가 아니라 "프루프가 다룬 모양에서 옳다"는 뜻이다 — 실측
 * (2026-08-30 전수 점검): `strict-additive-writes` 는 초록 프루프를 뒤에 두고도 편집 2,923건 중
 * 91% 에서 무동작이었다. 프루프가 자기가 아는 모양만 태웠기 때문이다. 이름조차 불리지 않은
 * 가드는 경계가 아무 데도 고정돼 있지 않다 — 커버리지는 못 재도 부재는 잰다.
 */
function guardsWithoutProof(root: string, proofDir: string, proofFiles: string[]): Issue[] {
  const guardDir = join(root, GUARDS);
  if (!existsSync(guardDir)) return [];
  const proofText = proofFiles.map((f) => readFileSync(join(proofDir, f), "utf-8")).join("\n");
  const issues: Issue[] = [];
  for (const guard of readdirSync(guardDir).filter((f) => f.endsWith(".ts")).sort()) {
    if (proofText.includes(guard)) continue;
    issues.push(`${GUARDS}/${guard}: 이름을 부르는 프루프가 없다 — ${DIR}/ 에 이 가드의 차단·통과 경계를 태우는 케이스를 넣는다`);
  }
  return issues;
}

export const check: Check = { name: "harness-proofs", run };
if (isMain(import.meta.url)) runCli(check);
