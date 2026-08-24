import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/**
 * Strict-No-Subagents Pre Hook
 *
 * Prevents creation of subagents via the `task` tool.
 * All multi-step work must be done by the main agent in a single turn.
 *
 * To add/remove rules: modify the denylist array. No other logic changes needed.
 */
export default function strictNoSubagents(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName?: string }) => {
    if (event.toolName !== "task") return;
    return {
      block: true,
      reason: "서브에이전트 생성 금지\n\n모든 작업은 현재 에이전트가 수행합니다.",
    };
  });
}
