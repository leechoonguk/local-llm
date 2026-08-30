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

    if (toolName !== "write" && toolName !== "edit") return;

    // 편집의 대상 경로는 세 모양으로 온다: 깨끗한 `path`, 내용 태그가 붙은 `path`
    // (`0072_add_notice.py#0D77`), 그리고 `path` 가 아예 없고 패치 본문 첫 줄의
    // `[상대경로#TAG]` 헤더에만 있는 형태. 앞의 둘만 읽으면 패치형 편집이 푸시된 리비전을
    // 그대로 고쳐도 이 가드는 경로를 못 봐서 통과시킨다. strict-additive-writes 와 같은
    // 해석을 쓴다 — 태그를 벗기고, 없으면 헤더에서 읽고, 그래도 없으면 fail-open.
    const patch = typeof event.input.input === "string" ? event.input.input : "";
    const header = /^\s*\[([^\]\n#]+)/.exec(patch);
    const path = String(event.input.path ?? "").replace(/#[0-9A-Fa-f]{4}$/, "") || (header?.[1] ?? "");
    if (path === "") return; // 경로를 못 읽으면 조용히 통과한다 — 훅은 절대 던지지 않는다
    if (!isMigrationPath(path)) return;

    // Hand-creating a revision file skips `make migrate-gen`'s auto-numbering.
    // Measured: a local model guessed occupied revision numbers (72/73) and thrashed
    // through ten filename variants before landing on a free one — the migrations
    // rule that says to use migrate-gen only fires on bash migration commands, which
    // a direct write never triggers. Enforce the workflow here, at the write itself.
    if (toolName === "write" && !existsSync(resolve(projectRoot, path))) {
      return {
        block: true,
        reason:
          "do not hand-create revision files — run `make migrate-gen m=\"<message>\"` " +
          "(the revision id auto-increments past every existing file). Edit the " +
          "generated revision afterwards if it needs adjusting.",
      };
    }

    if (!isPushedMigration(path)) return;

    return {
      block: true,
      reason:
        "pushed migration is immutable — create a new revision for the correction. " +
        "Unpushed migration files remain editable.",
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
