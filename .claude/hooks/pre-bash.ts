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
import { ask, deny, guarded, readHookInput } from "./lib/hook-io.ts";

/** 명령 위치. heredoc 본문 줄도 "줄 시작" 이라 잡힐 수 있지만, 규칙 문장은 보통 `- ` 나 백틱으로 시작한다. */
// 백틱은 뺀다 — 명령 치환보다 마크다운 인용(`brew services …` 금지)이 훨씬 잦아 규칙 파일 편집을 막았다.
const AT = String.raw`(?:^|[;&|]\s*|\$\(\s*|\n\s*)`;
const cmd = (body: string): RegExp => new RegExp(`${AT}(?:env\\s+(?:\\w+=\\S*\\s+)*)?${body}`, "m");

// 다운로드/설치 deny(ollama pull, hf/huggingface-cli download, install.sh)는 2026-08-25 제거했다 —
// 사용자가 에이전트의 모델 다운로드를 명시 허용. brew services·sudo 가드만 남긴다(자동 재시작 금지·권한 안전).
export const FORBIDDEN: Array<{ re: RegExp; reason: string }> = [
  { re: cmd(String.raw`brew\s+services\s+(?:start|restart|run)\s+(?:\S+/)?(?:ollama|omlx)\b`), reason: "규칙 6: brew services 로 Ollama/oMLX 를 띄우지 않는다(KeepAlive/RunAtLoad true = 자동 재시작). 레포 LaunchAgent 를 launchctl kickstart 로 띄운다 — .claude/rules/autostart.md" },
  // `omlx start|restart|run|serve|launch` 는 실측(2026-08-25) brew services(homebrew.mxcl.omlx)를 조작하거나
  // 별도 headless 서버를 띄운다 — 둘 다 GUI 앱(oMLX.app)과 충돌하고 규칙 6 위반. oMLX 서버는 앱 메뉴바로만
  // 띄운다(벤치는 앱 서버로 검증). `omlx stop`·`omlx diagnose` 는 정리·진단용이라 허용한다.
  { re: cmd(String.raw`(?:\S*/)?omlx(?:-cli)?\s+(?:start|restart|run|serve|launch)\b`), reason: "oMLX 서버는 GUI 앱(oMLX.app) 메뉴바 Start 로만 띄운다 — `omlx start/restart`(brew services·별도 서버)는 규칙 6 위반이고 앱 서버와 충돌한다. .claude/rules/autostart.md" },
  { re: cmd(String.raw`sudo\s`), reason: "규칙 7: sudo 는 사용자가 직접 실행한다. 명령을 제시하고 기다릴 것." },
];

// 규칙 8: 커밋/푸시는 사용자 요청 시에만(2026-08-26 사용자 지시로 훅 강제). 훅은 "요청이 있었는지"를
// 알 수 없으므로 deny 가 아니라 ask 로 올린다 — 요청받은 커밋이면 사용자가 그 자리에서 승인하면 된다.
// 패턴은 자기 가드다(우회 방지가 아니라 실수 방지) — 흔한 형태(git commit/push, 플래그 선행)만 본다.
export const GATED: Array<{ re: RegExp; reason: string }> = [
  { re: cmd(String.raw`git\s+(?:-\S+\s+)*(?:commit|push)\b`), reason: "규칙 8: 커밋/푸시는 사용자 요청 시에만 한다. 사용자가 방금 요청한 커밋/푸시라면 승인하면 된다." },
];

guarded("pre-bash", () => {
  const input = readHookInput();
  const command = input.tool_input?.command ?? "";
  if (command === "") return;
  for (const f of FORBIDDEN) if (f.re.test(command)) deny("PreToolUse", `${f.reason}\n명령: ${command.split("\n")[0]}`);
  for (const g of GATED) if (g.re.test(command)) ask("PreToolUse", `${g.reason}\n명령: ${command.split("\n")[0]}`);
});
