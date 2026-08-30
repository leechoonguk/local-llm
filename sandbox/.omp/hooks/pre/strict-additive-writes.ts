/**
 * Strict-Additive-Writes Pre Hook
 *
 * An additive task must not wipe existing code. Measured failure class: asked
 * to ADD a domain, a local model rewrote a shared file and dropped lines that
 * other domains depended on (alembic/env.py lost the `user` model import —
 * recorded as a destructive regression). The write/edit path that loses the
 * most at once is a full-file `write` onto an existing source file; the shell
 * twin is a `>` truncation. Both are blocked with guidance toward targeted
 * edits — `edit` changes survive, wholesale rewrites forget.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { resolve } from "node:path";

const MIN_LINES = 12;        // files smaller than this are cheap to rewrite honestly
const RETAIN_FLOOR = 0.5;    // block when less than half of the existing lines survive

export default function strictAdditiveWrites(pi: any) {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    const toolName = String(event.toolName ?? "");

    if (toolName === "bash" || toolName === "eval") {
      const body = String(event.input.command ?? event.input.code ?? "");
      const m = body.match(/(?<![>\d&])>\s*([\w@./-]+\.(?:py|ts|tsx|js|mjs|md|yml|yaml|toml|json|http))\b/);
      if (!m) return;
      const abs = resolve(process.cwd(), m[1]);
      if (!existsSync(abs)) return;
      if (countLines(abs) < MIN_LINES) return;
      return {
        block: true,
        reason:
          `\`> ${m[1]}\` truncates an existing file — append with >>, or use the edit tool ` +
          "for targeted changes. An additive task must not wipe existing content.",
      };
    }

    if (toolName === "edit" && typeof (event.input as any).input === "string") {
      // omp 18 patch form, measured 2026-08-28: {path, input: "[rel#TAG]\nPUT 12.:\n+line..."}.
      // Grammar observed in sessions: `PUT N:`/`PUT N.:` REPLACE line N; `PUT N+k@:`/`PUT N+k:`
      // INSERT after line N. The services.py wholesale swap (User->Notice, 7th observation of
      // the replace-instead-of-add habit — frontier models do it in omp too) arrived as a
      // replace-form PUT on the user import line. Destruction is blocked, not advised.
      const patch = String((event.input as any).input);
      // 경로는 세 곳에 있을 수 있다: `path`(깨끗), `path`+내용 태그(`main.py#0D77`), 또는 패치 본문의
      // `[상대경로#TAG]` 헤더. 전수 점검(2026-08-30): 편집 2,923건 중 2,230건은 `path` 자체가 없고
      // 440건은 태그가 붙어 있었다 — 둘 다 fail-open 으로 빠져서 이 가드는 **91% 무동작**이었다.
      const header = /^\s*\[([^\]\n#]+)/.exec(patch);
      const rawPath = String(event.input.path ?? "").replace(/#[0-9A-Fa-f]{4}$/, "") || (header?.[1] ?? "");
      const path = rawPath;
      const abs = path.startsWith("/") ? path : resolve(process.cwd(), path);
      const fileText = safeRead(abs);
      if (fileText === null) return; // 빈 path→cwd(디렉터리) 등 — EISDIR 클래스 fail-open
      const fileLines = fileText.split("\n");
      const isImport = (l: string) => /^(from\s+\S+\s+import\b|import\s+\S)/.test(l);
      // 의도 프로토콜(사용자 설계 2026-08-28): 차단은 "실수 교체"만 걸러내는 장치다.
      // 진짜 교체 의도는 편집에 `# intent: replace` 마커를 실어 명시하면 통과한다 —
      // 추가를 원하면 삽입형으로, 교체를 원하면 선언하고 교체한다.
      const intendedReplace = /#\s*intent:\s*replace/i.test(patch);
      // 본문 줄의 `+` 접두는 **선택**이다 — 배포 셀에서 접두 없는 형식(`PUT 233:\n api_router...`)
      // 으로 등록 줄이 교체됐는데 파서가 통째로 놓쳤다(2026-08-28 실측, 회귀 1건).
      // 삭제형(`CUT N`, `CUT N.=M`)은 문법에 아예 없었다 — 등록 줄을 지우는 가장 직접적인 형태인데
      // 통과했다(전수 점검에서 154건/66세션). 지운 줄이 등록·import 면 막는다.
      if (!intendedReplace) {
        for (const cut of patch.matchAll(/(?:^|\n)CUT (\d+)(?:\.?=(\d+))?/g)) {
          const from = Number(cut[1]), to = Number(cut[2] ?? cut[1]);
          for (let n = from; n <= to; n++) {
            const line = (fileLines[n - 1] ?? "").trim();
            if (line && isRegistrationLine(line)) {
              return {
                block: true,
                reason: `\`${path}\` ${n}행을 지운다 — 그 줄은 등록/배선이다(\`${line.slice(0, 60)}\`). ` +
                  "추가 과제에서 기존 등록은 남는다. 정말 지워야 하면 편집에 `# intent: replace` 를 실어라.",
              };
            }
          }
        }
      }
      // `PUT N.=M:` 은 N..M 을 통째로 갈아끼우는 범위 교체다. 전수 점검에서 **1,109건/131세션**으로
      // 가장 흔한 교체 형태인데 예전 문법이 못 잡았다. 범위의 모든 줄을 대상으로 본다.
      for (const op of patch.matchAll(/(?:^|\n)PUT (\d+)(\+\d+@?)?(?:\.?=(\d+))?\.?:\n((?:(?!PUT \d|CUT \d)[^\n]*(?:\n|$))+)/g)) {
        if (op[2]) continue; // insert form — additive, fine
        if (intendedReplace) continue; // declared intent — the replacement stands
        const rangeEnd = Number(op[3] ?? op[1]);
        const bodyAll = op[4].split("\n").map((l) => l.replace(/^\+/, "").trim()).filter(Boolean);
        for (let n = Number(op[1]); n <= rangeEnd; n++) {
          const covered = (fileLines[n - 1] ?? "").trim();
          if (covered && isRegistrationLine(covered) && losesEntries(covered, bodyAll.join("\n"))) {
            const lost = registrationEntries(covered).filter((e) => !bodyAll.join("\n").includes(e));
            return {
              block: true,
              reason: `\`${path}\` ${n}행의 등록이 사라진다 — \`${lost.join(", ").slice(0, 60)}\` 가 새 내용에 없다. ` +
                "기존 항목을 모두 유지한 채 새 이름을 더하라. 정말 지워야 하면 `# intent: replace` 를 실어라.",
            };
          }
        }
        const target = (fileLines[Number(op[1]) - 1] ?? "").trim();
        if (!target) continue;
        const bodyLines = op[4].split("\n").map((l) => l.replace(/^\+/, "").trim()).filter(Boolean); // 접두 있으면 벗기고, 없으면 그대로
        const retained = bodyLines.includes(target);
        if (retained) continue;
        // 보편 규칙: 형제 치환(sibling swap). 관측된 7건 전부 "뼈대는 같고 식별자만
        // 다른" 줄로의 교체였다(user->notice). 프레임워크 무관: 식별자 마스킹 후
        // 뼈대가 동일하고 식별자가 2군데 이상 갈리면, 추가 과제에서 형제는 공존해야
        // 한다 — 교체가 아니라 삽입으로 유도한다. (값 수정 x=1->x=2, 단일 인자 교체
        // compute(y)->compute(z) 는 통과 — 오탐 경계는 프루프 15-19.)
        // 등록/배선 줄은 **누적되는 것**이라 교체 자체가 사고다 — 식별자 하나만 바뀌어도
        // (include_router(user) → include_router(notice)) 다른 도메인이 라우팅에서 사라진다.
        // 2026-08-28 배포 셀에서 정확히 이 형태로 회귀 1건이 났고, 형제치환 규칙(식별자 2개
        // 이상)에는 안 걸렸다. 경로 목록이 아니라 **줄 모양**으로 판정한다(프레임워크 무관).
        // 등록 줄은 **누적된다** — 그래서 판정은 "같은가"가 아니라 "잃었는가"다. 한 줄짜리 import
        // 목록에 이름을 더하려면 그 줄을 고칠 수밖에 없으므로, 글자 동일성을 요구하면 정당한 배선이
        // 통째로 막힌다(2026-08-30 실측: 그 상태에서 세션이 라우터 등록을 끝내지 못했다).
        if (isRegistrationLine(target) && losesEntries(target, bodyLines.join("\n"))) {
          const lost = registrationEntries(target).filter((e) => !bodyLines.join("\n").includes(e));
          return {
            block: true,
            reason:
              `this edit drops \`${lost.join(", ").slice(0, 60)}\` from a registration line ` +
              `(\`${target.slice(0, 70)}\`) — registries accumulate: keep every existing entry and add yours ` +
              "alongside. If removal is truly intended, resend with a `# intent: replace` comment line.",
          };
        }
        const sibling = bodyLines.find((b) => siblingSwap(target, b));
        if (sibling) {
          return {
            block: true,
            reason:
              `this edit REPLACES \`${target.slice(0, 60)}\` with its sibling \`${sibling.slice(0, 60)}\` — ` +
              "if you meant to ADD, keep the old line and use the insert form " +
              `(\`PUT ${op[1]}+1@:\`) for the new one. If you truly mean to REPLACE it, resend the same ` +
              "edit with a `# intent: replace` comment line included.",
          };
        }
        if (isImport(target) && bodyLines.some(isImport) && losesEntries(target, bodyLines.join("\n"))) {
          return {
            block: true,
            reason:
              `this edit replaces an existing import (\`${target.slice(0, 60)}\`) with a new one — ` +
              "if you meant to ADD, keep the old line and insert yours next to it " +
              `(\`PUT ${op[1]}+1@:\`). If you truly mean to replace it, resend with a \`# intent: replace\` comment.`,
          };
        }
      }
      return;
    }

    if (toolName === "edit") {
      // Legacy field shape: {path, old_string, new_string}
      // or {path, edits: [{old_string, new_string}]}.
      const pairs: Array<{ old_string?: unknown; new_string?: unknown }> =
        Array.isArray((event.input as any).edits) ? (event.input as any).edits : [event.input as any];
      for (const pr of pairs) {
        const oldStr = String(pr.old_string ?? "");
        const newStr = String(pr.new_string ?? "");
        if (!oldStr) continue;
        // (a) Replacing an existing import line — the measured env.py class:
        // asked to ADD a model import, the model swapped the `User` line for
        // `Notice`. A replaced import is wiped code; add alongside instead.
        const oldImports = meaningfulLines(oldStr).filter((l: string) => /^(from\s+\S+\s+import\b|import\s+\S)/.test(l));
        const dropped = oldImports.filter((l: string) => !newStr.includes(l));
        const addsImport = /(^|\n)\s*(from\s+\S+\s+import\b|import\s+\S)/.test(newStr);
        if (dropped.length > 0 && addsImport) {
          return {
            block: true,
            reason:
              `this edit replaces an existing import (\`${String(dropped[0]).slice(0, 60)}\`) with a new one — ` +
              "an additive task adds its import alongside; existing imports register models/behavior " +
              "other code depends on. Keep the old line and add yours next to it.",
          };
        }
        // (b) Unwrapping surviving code: deleting a context/try wrapper line
        // while its body stays. Measured class: `async with self.session.begin():`
        // removed from an existing service, silently dropping transaction
        // management — a small edit invisible to the other rules.
        const wrapper = (l: string) => /^(?:async\s+)?with\b.*:$/.test(l) || /^try\s*:$/.test(l);
        const newSetW = new Set(meaningfulLines(newStr));
        const droppedWrappers = meaningfulLines(oldStr).filter((l: string) => wrapper(l) && !newSetW.has(l));
        const retainedOthers = meaningfulLines(oldStr).filter((l: string) => !wrapper(l) && newSetW.has(l)).length;
        if (droppedWrappers.length > 0 && retainedOthers > 0) {
          return {
            block: true,
            reason:
              `this edit removes \`${String(droppedWrappers[0]).slice(0, 60)}\` while keeping the code it wraps — ` +
              "an additive task must not strip existing context/transaction wrappers from surviving code.",
          };
        }
        // (c) Egregious deletion: a large block mostly vanishes.
        const oldLines = meaningfulLines(oldStr);
        if (oldLines.length >= 8) {
          const newLines = meaningfulLines(newStr);
          const newSet = new Set(newLines);
          const retained = oldLines.filter((l: string) => newSet.has(l)).length / oldLines.length;
          // A wholesale MODIFICATION keeps the block's size (every line changed,
          // e.g. a rename sweep) — that is not a deletion. Only a block that
          // actually SHRINKS below half its size counts as a wipe.
          if (retained < 0.3 && newLines.length < oldLines.length * 0.5) {
            return {
              block: true,
              reason:
                `this edit deletes ~${Math.round((1 - retained) * 100)}% of a ${oldLines.length}-line block — ` +
                "an additive task must not wipe existing code; make a narrower edit that keeps unrelated lines.",
            };
          }
        }
      }
      return;
    }

    if (toolName !== "write") return;
    // 내용 태그(`main.py#0D77`)가 붙어 오면 확장자 판정이 빗나가 이 가드가 조용히 통과한다.
    const path = String(event.input.path ?? "").replace(/#[0-9A-Fa-f]{4}$/, "");
    if (!/\.(?:py|ts|tsx|js|mjs|yml|yaml|toml|json|http)$/.test(path)) return;
    const abs = resolve(process.cwd(), path);
    const fileText = safeRead(abs);
    if (fileText === null) return;
    const oldLines = meaningfulLines(fileText);
    if (oldLines.length < MIN_LINES) return;
    const newSet = new Set(meaningfulLines(String(event.input.content ?? event.input.text ?? "")));
    const retained = oldLines.filter((l: string) => newSet.has(l)).length / oldLines.length;
    if (retained >= RETAIN_FLOOR) return;
    return {
      block: true,
      reason:
        `overwriting ${path} drops ~${Math.round((1 - retained) * 100)}% of its existing lines — ` +
        "the task adds code, it does not replace the file. Use the edit tool for targeted " +
        "changes, or include the existing content you mean to keep.",
    };
  });
}

/** 등록·배선 줄(누적되는 레지스트리 항목)인가 — 경로가 아니라 모양으로 판정한다. */
/**
 * 등록 줄이 담고 있던 **항목**들. import 목록의 이름, `include_router(x.router)` 의 `x`,
 * `XDep = Annotated[...]` 의 좌변처럼 "누적되는 것"을 뽑는다.
 */
function registrationEntries(line: string): string[] {
  const imp = /^from\s+\S+\s+import\s+(.+)$/.exec(line);
  if (imp) return imp[1].split(",").map((x) => x.trim().replace(/\s+as\s+\S+$/, "")).filter(Boolean);
  const call = /\b(?:include_router|add_middleware|add_api_route|register|add_url_rule|mount)\s*\(\s*([A-Za-z_][\w.]*)/.exec(line);
  if (call) return [call[1]];
  const dep = /^(\w+Dep)\s*=/.exec(line);
  if (dep) return [dep[1]];
  const plain = /^import\s+(\S+)/.exec(line);
  if (plain) return [plain[1]];
  return [line];
}

/**
 * 교체가 **손실인가**. 항목이 하나도 사라지지 않으면 손실이 아니다.
 *
 * 이 판정이 "옛 줄이 글자 그대로 남아 있는가" 였을 때, `from app.routers import a, b` 에 이름을
 * 하나 더하는 정당한 편집이 막혔다 — 한 줄짜리 목록에서 "나란히 추가"는 그 줄을 고치는 것뿐인데,
 * 안내는 실행 불가능한 지시를 하고 있었다(2026-08-30 실측: 배선 단계에서 세션이 갇혔다).
 */
function losesEntries(oldLine: string, bodyText: string): boolean {
  return registrationEntries(oldLine).some((e) => !new RegExp(`(^|[^\\w.])${e.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^\\w]|$)`).test(bodyText));
}

function isRegistrationLine(l: string): boolean {
  return /^(from\s+\S+\s+import\b|import\s+\S)/.test(l)
    || /^\w+Dep\s*=\s*Annotated\b/.test(l)
    || /\b(include_router|add_middleware|add_api_route|register|add_url_rule|mount)\s*\(/.test(l);
}

function siblingSwap(oldLine: string, newLine: string): boolean {
  if (oldLine === newLine) return false;
  const ids = (l: string) => l.match(/[A-Za-z_][A-Za-z0-9_]*/g) ?? [];
  const skel = (l: string) => l.replace(/[A-Za-z_][A-Za-z0-9_]*/g, "\u0001").replace(/\s+/g, " ").trim();
  if (skel(oldLine) !== skel(newLine)) return false;
  const a = ids(oldLine), b = ids(newLine);
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) diff++;
  return diff >= 2;
}

// 훅은 절대 던지지 않는다 — omp 는 훅 예외를 도구 실패로 승격시켜 edit 자체를
// 죽인다(실측 2026-08-28: EISDIR 크래시 13/13 로 한 셀의 edit 이 전멸, ~10분 낭비).
// 읽을 수 없거나 파일이 아니면 null → 검사를 조용히 통과(fail-open).
function safeRead(p: string): string | null {
  try {
    const st = statSync(p);
    if (!st.isFile()) return null;
    return readFileSync(p, "utf-8");
  } catch { return null; }
}

function meaningfulLines(content: string): string[] {
  return content.split("\n").map((l: string) => l.trim()).filter((l: string) => l !== "");
}

function countLines(path: string): number {
  try { return meaningfulLines(readFileSync(path, "utf-8")).length; } catch { return 0; }
}
