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
  // `omlx start|restart|run|serve|launch` 는 실측(2026-08-25) brew services(homebrew.mxcl.omlx)를 조작하거나
  // 별도 headless 서버를 띄운다 — 둘 다 GUI 앱(oMLX.app)과 충돌하고 규칙 6 위반. 단 **앱 셔틀**
  // `~/.omlx/bin/omlx` 는 CLAUDE.md 가 문서화한 제어 경로("omlx start|stop|restart 로 제어")라 예외다
  // — 2026-08-27 실측: admin `/reload` 는 프로파일 라우트를 떨어뜨려 레지스트리 변경 반영엔 셔틀 재시작이 필요.
  { re: cmd(String.raw`(?:\S*/)?(?<!\.omlx/bin/)omlx(?:-cli)?\s+(?:start|restart|run|serve|launch)\b`), reason: "oMLX 서버는 GUI 앱(oMLX.app) 또는 앱 셔틀(~/.omlx/bin/omlx)로만 제어한다 — brew omlx-cli 의 start/restart 는 규칙 6 위반이고 앱 서버와 충돌한다. .claude/rules/autostart.md" },
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
