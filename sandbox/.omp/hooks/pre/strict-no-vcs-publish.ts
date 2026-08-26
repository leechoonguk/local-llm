/**
 * Strict-No-VCS-Publish Pre Hook
 *
 * Version control belongs to the user (sticky RULES.md, Session Safety: "Never
 * commit or push unless the user explicitly asks"). A hook cannot see intent,
 * but in this workspace the constraint is exact: benched sessions are headless
 * and their briefings never request a commit — and this subject tree is not a
 * git repository (the enclosing repo tracks it), so any git commit/push here
 * would mutate the enclosing repository. Deny outright; strict-verified-git
 * stays as the quality gate for workspaces where publishing is legitimate.
 */

const GIT_PUBLISH = /(?:^|[&|;()]\s*)(?:sudo\s+)?git(?:\s+-\S+(?:\s+\S+)?)*\s+(?:commit|push)\b/;

export default function strictNoVcsPublish(pi: any) {
  pi.on("tool_call", (event: { toolName?: string; input?: Record<string, unknown> }, _ctx: unknown) => {
    if (event.toolName !== "bash" && event.toolName !== "eval") return;
    const command = String(event.input?.command ?? event.input?.code ?? "");
    if (!GIT_PUBLISH.test(command)) return;
    return {
      block: true,
      reason:
        "git commit/push is user-only in this workspace (RULES.md, Session Safety). " +
        "Leave the worktree as the deliverable; the user publishes it.",
    };
  });
}
