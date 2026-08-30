#!/usr/bin/env node
/**
 * sandbox 하네스 점검 규칙의 경계 검사 — `make check-sandbox-harness-review`.
 *
 * 지키는 것 하나: **피험자 트리의 규칙은 자기 밖을 가리키지 않는다.** `sandbox/.omp/rules/*.md` 가
 * `bench/`·`.claude/` 경로나 벤치 어휘(셀·캠페인·세션 코퍼스)를 쓰면, 그 프로젝트의 표준 문서가
 * 바깥 실험을 알아야 하는 문서가 된다. 측정과 판정은 이 워크스페이스에 남는다.
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
const RULES = join(ROOT, "sandbox", ".omp", "rules");
// 경로뿐 아니라 **실험 어휘**도 막는다 — 첫 판은 경로만 보다가 RULES.md 의 "풀링 n=11", "역대 최속 셀"
// 같은 문장을 통과시켰다. 프로젝트 표준 문서는 자기 규칙을 말하지, 우리 실험을 인용하지 않는다.
const OUTWARD = /\.claude\/|(^|\s)bench\/|llm-bench|세션 코퍼스|캠페인|벤치|역대 최속|풀링 n=|측정 n=|셀에서 실측/;
const issues: string[] = [];

// 규칙 디렉터리뿐 아니라 sticky 문서(RULES.md·AGENTS.md)도 본다 — 첫 판에서 그 둘을 빼놓았고,
// 실제로 벤치 어휘가 RULES.md 로 새어 들어가 있었다.
const targets: string[] = [];
for (const extra of ["RULES.md", "AGENTS.md"]) {
  const abs = join(ROOT, "sandbox", ".omp", extra);
  if (existsSync(abs)) targets.push(abs);
}
if (existsSync(RULES)) {
  for (const f of readdirSync(RULES).filter((n) => n.endsWith(".md"))) targets.push(join(RULES, f));
}
{
  for (const abs of targets) {
    const f = abs.replace(join(ROOT, "sandbox", ".omp") + "/", "");
    const lines = readFileSync(abs, "utf-8").split("\n");
    lines.forEach((line, i) => {
      if (OUTWARD.test(line)) {
        issues.push(`sandbox/.omp/${f}:${i + 1}: 피험자 트리의 규칙이 바깥 워크스페이스를 가리킨다 — 측정·판정은 bench/ 와 .claude/rules/sandbox-harness-review.md 에 둔다`);
      }
    });
  }
}

if (issues.length > 0) {
  console.error("check-sandbox-harness-review: " + issues.join("\ncheck-sandbox-harness-review: "));
  process.exit(1);
}
console.log("check-sandbox-harness-review: OK");
