/**
 * Strict-No-Harness-Edit Pre Hook
 *
 * 피험자는 자기를 채점하는 하네스를 고칠 수 없다. 실측(2026-08-29, 프롬프트 단위 프로브):
 * 모델이 `q: NameQuery | None` 을 통과시키려고 검사 자체(`check-backend-router-params.ts`)의
 * 판정 정규식을 고쳤다 — 코드가 아니라 자를 바꾼 것이다. 게이트가 초록이어도 그 초록은 거짓이다.
 *
 * 막는 것: `.omp/` 아래 파일의 편집·생성(도구 경로 기준)과, 셸에서 같은 경로로 향하는
 * 흔한 쓰기 모양(리다이렉션, `sed -i`, `tee`, `cp`/`mv`, `rm`). 검사가 틀렸다고 판단되면
 * 고치지 말고 답변에 적어 사용자에게 보고한다 — 그게 이 하네스의 계약이다.
 */

const HARNESS_PATH = /(^|\/)\.omp\//;
const SHELL_WRITE = [
  // 쓰기 동사 + 같은 명령 안의 `.omp/` 경로. 인용부호 안에 `|` 가 들어와도 끊기지 않게
  // 구분자 클래스가 아니라 줄 단위로 본다(2026-08-29: `sed -i '' 's/Query$/Query|None/'` 가 샜다).
  /(?:^|[&|;()]\s*)(?:sudo\s+)?(?:sed\s[^\n]*-i|tee|cp|mv|rm|install|truncate|dd)\b[^\n]*\.omp\//,
  />>?\s*[^\s|;&]*\.omp\//,
];

const REASON =
  "이 경로는 하네스다 — 피험자는 자기를 채점하는 검사·훅·확장을 고칠 수 없다. " +
  "검사가 틀렸다고 보이면 파일을 고치지 말고, 무엇이 왜 틀렸는지 답변에 적어 보고하라. " +
  "코드를 검사에 맞추는 것이 이 과제의 일이다.";

export default function strictNoHarnessEdit(pi: any) {
  pi.on("tool_call", (event: { toolName?: string; input?: Record<string, unknown> }, _ctx: unknown) => {
    const tool = String(event.toolName ?? "");
    if (/^(write|edit|patch|multiedit|apply_patch)/i.test(tool)) {
      const path = String(event.input?.path ?? event.input?.file_path ?? event.input?.filePath ?? "");
      if (path && HARNESS_PATH.test(path)) return { block: true, reason: `\`${path}\` — ${REASON}` };
      return;
    }
    if (tool === "bash" || tool === "eval") {
      const command = String(event.input?.command ?? event.input?.code ?? "");
      if (SHELL_WRITE.some((re) => re.test(command))) return { block: true, reason: REASON };
    }
  });
}
