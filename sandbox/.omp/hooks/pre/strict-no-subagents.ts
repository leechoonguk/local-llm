import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/**
 * Strict-No-Subagents Pre Hook
 *
 * Prevents creation of subagents via the `task` tool.
 *
 * 이 워크스페이스는 로컬 모델 한 슬롯으로 돌아간다. 서브에이전트는 같은 GPU 를 나눠 쓰므로 본 작업이
 * 그만큼 멈추고, 새 에이전트는 이 프로젝트의 규칙서와 훅 계약을 처음부터 다시 읽어야 한다 — 비용은
 * 두 배인데 문맥은 반이다. 병렬이 필요하면 도구 호출을 한 턴에 묶는다(RULES.md, Subagents).
 *
 * To add/remove rules: modify the denylist array. No other logic changes needed.
 */
export default function strictNoSubagents(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName?: string }) => {
    if (event.toolName !== "task") return;
    return {
      block: true,
      reason: "서브에이전트 생성 금지 — 이 워크스페이스는 로컬 모델 한 슬롯이라 새 에이전트는 같은 GPU 를 나눠 쓰고 문맥을 처음부터 다시 쌓는다.\n\n모든 작업은 현재 에이전트가 수행하고, 병렬이 필요하면 도구 호출을 한 턴에 묶는다.",
    };
  });
}
