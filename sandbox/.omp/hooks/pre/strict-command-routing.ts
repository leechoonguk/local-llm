import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/**
 * Strict-Command-Routing Pre Hook
 *
 * All commands that have a `make` target must use `make <target>`.
 * Direct tool invocations (ruff, pytest, pyright, npx, docker-compose)
 * and port killing are blocked.
 *
 * Denylist patterns are anchored to a command boundary (line start, or after
 * `&&` / `||` / `;` / `|` / `(`, with optional `sudo`). A binary path used as
 * an argument — e.g. `ls backend/.venv/bin/ruff` — is NOT an invocation and
 * is not blocked.
 *
 * To add/remove rules: modify the denylist array. No other logic changes needed.
 */
export default function strictCommandRouting(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName?: string; input?: Record<string, unknown> }) => {
    if (event.toolName !== "bash") return;

    const cmd = String(event.input?.command ?? "");

    // --- Allowlist ---
    if (cmd.startsWith("make ")) return;

    // --- Denylist (patterns anchored to a command boundary) ---
    for (const rule of denylist) {
      if (rule.pattern.test(cmd)) {
        return {
          block: true,
          reason: `\`${rule.desc}\` — 직접 실행 금지\n\nmake 타겟을 사용하세요:\n  → \`${rule.target}\``,
        };
      }
    }
  });
}

/**
 * Anchors the given binary name to a command boundary (start or after `&&`, `||`, `;`, `|`, `(`, optional `sudo`).
 * Allows whitespace-free relative-path prefixes (`backend/`, `./`, `repo/pkg/`), but never an argument word —
 * e.g. `ls backend/.venv/bin/ruff` stays unblocked because `ls ` (with space) cannot be part of the prefix.
 */
const atCmdStart = (bin: string) => `(?:^|[&|;()]\\s*)(?:sudo\\s+)?(?:[^\\s&|;()]+/)*${bin}\\b`;

const denylist: Array<{
  desc: string;
  pattern: RegExp;
  target: string;
}> = [
  {
    desc: "Alembic 직접 실행",
    pattern: new RegExp(`${atCmdStart("\\.venv/bin/alembic")}(?:\\s|$)`),
    target: "make migrate",
  },
  {
    // ruff 자동수정·포맷터가 alembic 을 건드리면 기존 마이그레이션 37개가 통째로
    // 재서식된다(2026-08-28 실측, +2256/-2413 순수 포맷 처닝). 마이그레이션은 불변.
    desc: "Ruff 자동수정/포맷을 alembic 에 실행",
    pattern: /\bruff\b[^|;&]*(?:--fix|\bformat\b)[^|;&]*\balembic\b|\bruff\b[^|;&]*\balembic\b[^|;&]*(?:--fix|\bformat\b)/,
    target: "make fix (app/tests 한정)",
  },
  {
    desc: "Pytest 직접 실행",
    pattern: new RegExp(`${atCmdStart("\\.venv/bin/pytest")}(?:\\s|$)`),
    target: "make test",
  },
  {
    desc: "Pyright 직접 실행",
    pattern: new RegExp(`${atCmdStart("\\.venv/bin/pyright")}(?:\\s|$)`),
    target: "make typecheck",
  },
  {
    desc: "Script 직접 실행",
    pattern: new RegExp(`${atCmdStart("(?:npx|bash|sh)")}\\s+\\S*scripts/`),
    target: "make <target>",
  },
  {
    desc: "npx tool 직접 실행",
    pattern: new RegExp(`${atCmdStart("npx")}\\s+(?:vite|eslint|tsc)\\b`),
    target: "make <target>",
  },
  {
    desc: "Docker compose 직접 실행",
    pattern: new RegExp(`${atCmdStart("docker")}\\s+compose\\b`),
    target: "make <target>",
  },
  {
    desc: "포트 killing",
    pattern: new RegExp(`${atCmdStart("lsof")}\\s+-ti:\\d+\\s*\\|\\s*xargs\\s+kill\\b`),
    target: "make down",
  },
];
