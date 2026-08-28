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
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { resolve } from "node:path";

// ---- WATCH SPEC (data, not engine) -------------------------------------
// 프로젝트별 배선/등록 관용구는 여기에 데이터로 선언한다. 엔진(패치 파싱·교체/삽입
// 판별·형제 치환 탐지)은 범용이고, 이 블록만 프로젝트에 맞게 바꾼다.
const WATCH_SPEC: Array<{ paths: RegExp; lines: RegExp[] }> = [
  {
    paths: /backend\/(alembic\/env\.py|tests\/conftest\.py|app\/dependencies\/services\.py|app\/main\.py)$/,
    lines: [
      /^(from\s+\S+\s+import\b|import\s+\S)/,
      /^\w+Dep\s*=\s*Annotated\b/,
      /\binclude_router\(/,
    ],
  },
];
const watchedLine = (abs: string, line: string): boolean =>
  WATCH_SPEC.some((w) => w.paths.test(abs) && w.lines.some((r) => r.test(line)));
// ------------------------------------------------------------------------

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
      const path = String(event.input.path ?? "");
      const abs = path.startsWith("/") ? path : resolve(process.cwd(), path);
      if (!existsSync(abs)) return;
      const fileLines = readFileSync(abs, "utf-8").split("\n");
      const isImport = (l: string) => /^(from\s+\S+\s+import\b|import\s+\S)/.test(l);
      // 의도 프로토콜(사용자 설계 2026-08-28): 차단은 "실수 교체"만 걸러내는 장치다.
      // 진짜 교체 의도는 편집에 `# intent: replace` 마커를 실어 명시하면 통과한다 —
      // 추가를 원하면 삽입형으로, 교체를 원하면 선언하고 교체한다.
      const intendedReplace = /#\s*intent:\s*replace/i.test(patch);
      for (const op of patch.matchAll(/(?:^|\n)PUT (\d+)(\+\d+@?)?\.?:\n((?:\+[^\n]*(?:\n|$))+)/g)) {
        if (op[2]) continue; // insert form — additive, fine
        if (intendedReplace) continue; // declared intent — the replacement stands
        const target = (fileLines[Number(op[1]) - 1] ?? "").trim();
        if (!target) continue;
        const bodyLines = op[3].split("\n").map((l) => l.replace(/^\+/, "").trim()).filter(Boolean);
        const retained = bodyLines.includes(target);
        if (retained) continue;
        // 보편 규칙: 형제 치환(sibling swap). 관측된 7건 전부 "뼈대는 같고 식별자만
        // 다른" 줄로의 교체였다(user->notice). 프레임워크 무관: 식별자 마스킹 후
        // 뼈대가 동일하고 식별자가 2군데 이상 갈리면, 추가 과제에서 형제는 공존해야
        // 한다 — 교체가 아니라 삽입으로 유도한다. (값 수정 x=1->x=2, 단일 인자 교체
        // compute(y)->compute(z) 는 통과 — 오탐 경계는 프루프 15-19.)
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
        if (watchedLine(abs, target)) {
          return {
            block: true,
            reason:
              `this edit REPLACES a registration/wiring line (\`${target.slice(0, 70)}\`) in a shared file — ` +
              "add yours ALONGSIDE instead: keep that line and use the insert form " +
              `(\`PUT ${op[1]}+1@:\`) to put the new line after it. If replacement is truly intended, ` +
              "resend with a `# intent: replace` comment line.",
          };
        }
        if (isImport(target) && bodyLines.some(isImport)) {
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
    const path = String(event.input.path ?? "");
    if (!/\.(?:py|ts|tsx|js|mjs|yml|yaml|toml|json|http)$/.test(path)) return;
    const abs = resolve(process.cwd(), path);
    if (!existsSync(abs)) return;
    const oldLines = meaningfulLines(readFileSync(abs, "utf-8"));
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

function meaningfulLines(content: string): string[] {
  return content.split("\n").map((l: string) => l.trim()).filter((l: string) => l !== "");
}

function countLines(path: string): number {
  try { return meaningfulLines(readFileSync(path, "utf-8")).length; } catch { return 0; }
}
