/**
 * pre-bash — PreToolUse(Bash). CLAUDE.md 규칙 6·7 을 명령 단계에서 막는다.
 *
 *  - `brew services start|restart|run ollama|omlx` (규칙 6: 레포 LaunchAgent 만, 자동 재시작 금지)
 *  - `sudo …`, `ollama pull …`, `hf download …`, `huggingface-cli download …`, `ollama/install.sh`, `omlx/install.sh`
 *    (규칙 7: 큰 다운로드·sudo 는 사용자가 직접 — 명령을 제시하고 기다린다)
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

export const FORBIDDEN: Array<{ re: RegExp; reason: string }> = [
  { re: cmd(String.raw`brew\s+services\s+(?:start|restart|run)\s+(?:\S+/)?(?:ollama|omlx)\b`), reason: "규칙 6: brew services 로 Ollama/oMLX 를 띄우지 않는다(KeepAlive/RunAtLoad true = 자동 재시작). 레포 LaunchAgent 를 launchctl kickstart 로 띄운다 — .claude/rules/autostart.md" },
  { re: cmd(String.raw`sudo\s`), reason: "규칙 7: sudo 는 사용자가 직접 실행한다. 명령을 제시하고 기다릴 것." },
  { re: cmd(String.raw`ollama\s+pull\b`), reason: "규칙 7: 모델 pull(>10GB)은 사용자가 직접 한다. 명령을 제시하고 기다릴 것." },
  { re: cmd(String.raw`(?:hf|huggingface-cli|\$HF)\s+download\b`), reason: "규칙 7: HF 모델 다운로드는 사용자가 직접 한다. 명령을 제시하고 기다릴 것." },
  { re: cmd(String.raw`(?:(?:bash|sh|zsh|source|\.)\s+)?(?:\./)?(?:ollama|omlx)/install\.sh\b`), reason: "규칙 7: install.sh 는 sudo·대용량 다운로드를 포함한다 — 사용자에게 실행을 맡길 것." },
];

guarded("pre-bash", () => {
  const input = readHookInput();
  const command = input.tool_input?.command ?? "";
  if (command === "") return;
  for (const f of FORBIDDEN) if (f.re.test(command)) deny("PreToolUse", `${f.reason}\n명령: ${command.split("\n")[0]}`);
});
