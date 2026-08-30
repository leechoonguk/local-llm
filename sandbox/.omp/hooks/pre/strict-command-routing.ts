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
    // 실행 채널은 셋이다: bash, eval(파이썬/JS 본문에서 subprocess.run·execSync), hub(op:start).
    // bash 만 보면 전수 점검 기준 32% 가 샌다(차단 185 vs 우회 87).
    const tool = String(event.toolName ?? "");
    if (!/^(bash|eval)$/.test(tool)) return;

    const cmd = String((event.input as any)?.command ?? (event.input as any)?.code ?? "");

    // eval 본문에서는 라우팅 대상이 인용부호 안에 들어간다(`subprocess.run(["pytest", …])`) — 셸용
    // 패턴이 못 잡는다. 전수 점검(2026-08-30): eval 로 85건/25세션이 우회했다. 실행 함수 + 대상 도구가
    // 같은 본문에 있으면 막고, 셸과 같은 안내(make 타깃)를 준다.
    if (tool === "eval") {
      const runner = /\b(subprocess\.(?:run|call|check_output|Popen)|execSync|spawnSync|os\.system)\b/;
      const routed = /\b(pytest|ruff|pyright|alembic|npm|npx|docker[-\s]compose)\b/;
      if (runner.test(cmd) && routed.test(cmd)) {
        return {
          block: true,
          reason:
            "도구를 eval 본문에서 직접 실행하지 않는다 — 셸에서 막히는 것과 같은 우회다. " +
            "프로젝트의 make 타깃을 쓰세요(`make verify`, `make test-fast t=\"tests/...\"`, `make lint`, `make migrate-gen m=\"...\"`).",
        };
      }
    }

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
    // 실측(2026-08-28): `python` not found → which python3 → 상대 .venv 경로 실패 →
    // 절대경로, 0.5m 우회. 어포던스는 있으므로 라우팅으로 바로 안내한다.
    desc: "bare python/pytest 직접 실행",
    // bare 는 경로 없는 호출만이다. atCmdStart 의 경로 접두를 쓰면 `backend/.venv/bin/python -c` 까지
    // 걸려, **이 규칙의 안내문이 권하는 바로 그 명령**을 자기가 막는다(전수 점검: 17건/10세션).
    // `.venv/bin/pytest` 도 여기서 먼저 걸려 아래 전용 규칙의 올바른 안내를 못 받았다(55건).
    pattern: /(?:^|[&|;()\n]\s*)(?:sudo\s+)?(?:python3?|pytest)\b(?:\s|$)/,
    target: 'make test-fast t="..." (단발 파이썬은 backend/.venv/bin/python 절대경로)',
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
