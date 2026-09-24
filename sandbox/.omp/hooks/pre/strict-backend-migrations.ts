import { writtenPaths } from "../lib/hook-tool-paths.ts";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { relative, resolve } from "node:path";
import {
  isPushedMigration as isUpstreamMigration,
  listPushedMigrationsMutatedBy,
} from "../lib/backend-migration-policy.ts";

const cwd = process.cwd();
const projectRoot = existsSync(resolve(cwd, "backend", "app")) ? cwd : resolve(cwd, "..");

/**
 * Strict-Backend-Migrations Pre Hook
 *
 * Allows edits to unpushed migration revisions. A migration becomes immutable
 * once its path exists on the branch's configured Git upstream.
 *
 * Immutability is about the file, not the tool that reaches it. Measured: a
 * local model told to follow the seed-naming rule renamed two published
 * revisions with `mv`, which the write/edit guard never sees - a rename is not a
 * write. So shell and eval bodies are read for the same policy.
 */
export default function strictBackendMigrations(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    const toolName = String(event.toolName ?? "");

    if (toolName === "bash" || toolName === "eval") {
      const body = String(event.input.command ?? event.input.code ?? "");
      const pushed = listPushedMigrationsMutatedBy(body);
      if (pushed.length === 0) return;
      return {
        block: true,
        reason:
          "pushed migration is immutable, and a rename or delete is not an exception — " +
          pushed.join(", ") +
          ". Create a new revision instead; renaming a published revision changes what every " +
          "other checkout already applied.",
      };
    }

    // 경로 판독은 lib/hook-tool-paths.ts 한 곳이다(fas 와 통합) — write 의 내용 태그
    // 스트립, edit 패치의 `[path#TAG]` 섹션 헤더 전부, MV 이동 대상까지. 이 가드가 자체 파서를
    // 갖고 있던 동안 fas 쪽에서는 edit 우회가 실측됐고(푸시 리비전 edit 재작성 무차단), 여기서는
    // 단일 경로만 읽어 다중 파일 패치의 둘째 파일부터 못 봤다. 빈 결과 = fail-open(훅은 안 던진다).
    const paths = writtenPaths(toolName, event.input).filter(isMigrationPath);
    if (paths.length === 0) return;

    // Hand-creating a revision file skips `make migrate-gen`'s auto-numbering.
    // Measured: a local model guessed occupied revision numbers (72/73) and thrashed
    // through ten filename variants before landing on a free one — the migrations
    // rule that says to use migrate-gen only fires on bash migration commands, which
    // a direct write never triggers. Enforce the workflow here, at the write itself.
    if (toolName === "write" && paths.some((p2) => !existsSync(resolve(projectRoot, p2)))) {
      return {
        block: true,
        reason:
          "do not hand-create revision files — run `make migrate-gen m=\"<message>\"` " +
          "(the revision id auto-increments past every existing file). Edit the " +
          "generated revision afterwards if it needs adjusting.",
      };
    }

    const pushed = paths.filter(isPushedMigration);
    if (pushed.length === 0) return;

    return {
      block: true,
      reason:
        "pushed migration is immutable — create a new revision for the correction (" +
        pushed.join(", ") +
        "). Unpushed migration files remain editable.",
    };
  });
}

function isMigrationPath(path: string): boolean {
  return relative(projectRoot, resolve(projectRoot, path)).startsWith("backend/alembic/versions/");
}

function isPushedMigration(path: string): boolean {
  const relativePath = relative(projectRoot, resolve(projectRoot, path));
  return isUpstreamMigration(relativePath);
}
