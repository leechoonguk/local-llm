/**
 * pre-bash — PreToolUse(Bash). CLAUDE.md 규칙 6·7 을 명령 단계에서 막는다.
 *
 *  - `brew services start|restart|run ollama|omlx` (규칙 6: 레포 LaunchAgent 만, 자동 재시작 금지)
 *  - `sudo …` (규칙 7: sudo 는 사용자가 직접 — 명령을 제시하고 기다린다)
 *
 * 모델 다운로드(`ollama pull`, `hf download`, `install.sh`) deny 는 2026-08-25 제거했다 —
 * 사용자가 에이전트의 대용량 모델 다운로드를 명시 허용.
 *
 * 패턴은 **명령 위치**(명령 시작, `;` `&&` `||` `|` `$(` 뒤, 줄 시작)에서만 본다. 문자열 인자나
 * heredoc 본문에 같은 단어가 나오는 것(규칙 파일에 "brew services 금지" 라고 쓰는 편집)은 막지 않는다 —
 * 이 훅을 처음 켰을 때 규칙 파일을 쓰는 heredoc 이 막혔던 것이 계기다.
 * deny 는 JSON `permissionDecision: "deny"` 로 낸다(exit 0). 다른 명령은 그대로 통과(출력 없음).
 * 검사 목록은 check-harness 의 스모크가 실제로 실행해 확인한다.
 */
import { deny, guarded, readHookInput } from "./lib/hook-io.ts";

/** 명령 위치. heredoc 본문 줄도 "줄 시작" 이라 잡힐 수 있지만, 규칙 문장은 보통 `- ` 나 백틱으로 시작한다. */
// 백틱은 뺀다 — 명령 치환보다 마크다운 인용(`brew services …` 금지)이 훨씬 잦아 규칙 파일 편집을 막았다.
const AT = String.raw`(?:^|[;&|]\s*|\$\(\s*|\n\s*)`;
const cmd = (body: string): RegExp => new RegExp(`${AT}(?:env\\s+(?:\\w+=\\S*\\s+)*)?${body}`, "m");

// 다운로드/설치 deny(ollama pull, hf/huggingface-cli download, install.sh)는 2026-08-25 제거했다 —
// 사용자가 에이전트의 모델 다운로드를 명시 허용. brew services·sudo 가드만 남긴다(자동 재시작 금지·권한 안전).
export const FORBIDDEN: Array<{ re: RegExp; reason: string }> = [
  { re: cmd(String.raw`brew\s+services\s+(?:start|restart|run)\s+(?:\S+/)?(?:ollama|omlx)\b`), reason: "규칙 6: brew services 로 Ollama/oMLX 를 띄우지 않는다(KeepAlive/RunAtLoad true = 자동 재시작). 레포 LaunchAgent 를 launchctl kickstart 로 띄운다 — .claude/rules/autostart.md" },
  // `omlx start|restart|run|serve|launch` 직접 호출은 전면 deny (2026-09-01 승격). 셔틀 예외를
  // 뒀었으나 실측이 뒤집었다: 셔틀 restart 가 앱 밖 고아 서버(PPID 1)를 만들었고 앱 재기동 뒤에도
  // 그 고아가 서빙했다. 유일한 정당 경로는 정본 관문 스크립트다(내부에서 stop→앱 확인→start→부모
  // 검증까지 한다). stop 단독은 무해해서 막지 않는다.
  { re: cmd(String.raw`(?:\S*/)?omlx(?:-cli)?\s+(?:start|restart|run|serve|launch)\b`), reason: "oMLX 기동/재기동은 정본 관문으로만 — `bash omlx/ensure-app-server.sh [--restart]` (셔틀 직접 restart 는 앱 밖 고아 서버를 만든다는 것이 실측됐다). .claude/rules/autostart.md" },
  { re: cmd(String.raw`sudo\s`), reason: "규칙 7: sudo 는 사용자가 직접 실행한다. 명령을 제시하고 기다릴 것." },
];

// git commit/push ask 게이트는 2026-08-27 제거 — 승인 프롬프트가 사용자에게 부담(사용자 결정,
// "omp 하네스에만 반영"). 규칙 8(요청 시에만)은 행동 규칙으로 유지되고, omp 쪽은
// sandbox/.omp/hooks/pre/strict-no-vcs-publish.ts 가 피험자의 커밋/푸시를 deny 한다.

guarded("pre-bash", () => {
  const input = readHookInput();
  const command = input.tool_input?.command ?? "";
  if (command === "") return;
  for (const f of FORBIDDEN) if (f.re.test(command)) deny("PreToolUse", `${f.reason}\n명령: ${command.split("\n")[0]}`);
});
