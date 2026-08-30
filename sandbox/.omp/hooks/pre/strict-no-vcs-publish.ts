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

// 벤치 셀에서는 VCS 로 과제 산출물을 **되살리는** 것도 막는다. 실측 2026-08-29(harnessv2 integration):
// 피험자가 Mode A 로 지워진 참조 구현을 `git checkout HEAD -- …` 로 복원하고 "make verify 통과"로
// 마쳤다 — 1248초, writes 2, 산출물 0/6. 게이트는 초록이었지만 측정된 것은 아무것도 없다.
// 인터랙티브에서는 정당한 작업이므로 셀 모드에서만 막는다(BENCH_CELL=1, 러너가 주입).
// 셀에서는 **읽기 경로로도** 정답에 닿을 수 없다. sandbox 에는 .git 이 없어 git 이 상위 레포로 올라가므로
// `git show HEAD:<경로>`·`git log -p`·`git diff HEAD` 가 지워진 참조 구현을 그대로 되살려 보여준다
// (2026-08-30 감사에서 열려 있음이 확인됐다 — 복원 차단만으로는 부족하다).
const GIT_READ = /(?:^|[&|;()\n'"]\s*)(?:sudo\s+)?git(?:\s+-\S+(?:\s+\S+)?)*\s+(?:show|diff|cat-file|blame|grep)\b|git\s+log\b[^\n]*\s-p\b/;
const GIT_RESTORE = /(?:^|[&|;()]\s*)(?:sudo\s+)?git(?:\s+-\S+(?:\s+\S+)?)*\s+(?:checkout|restore|stash|revert|reset)\b/;

export default function strictNoVcsPublish(pi: any) {
  pi.on("tool_call", (event: { toolName?: string; input?: Record<string, unknown> }, _ctx: unknown) => {
    if (event.toolName !== "bash" && event.toolName !== "eval") return;
    const command = String(event.input?.command ?? event.input?.code ?? "");
    if (process.env.BENCH_CELL === "1" && GIT_READ.test(command)) {
      return {
        block: true,
        reason:
          "이 세션은 벤치 셀이다 — VCS 히스토리에는 지워진 참조 구현이 그대로 있다. " +
          "명세와 남아 있는 형제 코드의 규약만으로 만들어야 한다.",
      };
    }
    if (process.env.BENCH_CELL === "1" && GIT_RESTORE.test(command)) {
      return {
        block: true,
        reason:
          "이 세션은 벤치 셀이다 — 과제 산출물을 VCS 에서 되살리는 것은 구현이 아니다. " +
          "지워진 파일은 명세와 남아 있는 코드의 규약을 보고 직접 만들어야 한다.",
      };
    }
    if (!GIT_PUBLISH.test(command)) return;
    return {
      block: true,
      reason:
        "git commit/push is user-only in this workspace (RULES.md, Session Safety). " +
        "Leave the worktree as the deliverable; the user publishes it.",
    };
  });
}
