import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import {
  SRC_DIRECTORIES,
  frontendSrc,
  label,
  projectRoot,
  readSources,
  walkSources,
} from "../lib/frontend-source.ts";
import { routerPathSegments } from "../lib/frontend-routes.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-API-Layer Post Hook
 *
 * Validates the transport and caching contract from
 * .omp/rules/frontend-api-layer.md:
 *
 *   1. one HTTP client — `axios.create` and `fetch` only in lib/api/client.ts
 *      (`ast-grep/rules/frontend-api/` owns the structural half)
 *   2. no URL literal outside lib/api/endpoints.ts
 *   3. services are transport only — no useQuery/useMutation in a service
 *   4. every query takes its key from a `*Keys` factory, never an array literal
 *   5. every list hook declares `placeholderData` — `usePagedRows` derives
 *      `hasNextPage` from the previous page, so losing it resets the grid
 *   6. every CRUD mutation invalidates its list key
 *   7. screens go through hooks — sections/ and pages/ never import a service
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

/** Only the client may build a transport or call the platform directly. */
const TRANSPORT_OWNER = "frontend/src/lib/api/client.ts";

/**
 * A path literal that looks like a backend route. The browser's own route
 * registry is exempt: its paths are URLs in this app, not in the API, and
 * `check-frontend-routing` owns them. The client is exempt for its 401
 * exemption list, which names auth paths on purpose.
 */
const URL_LITERAL_EXEMPT: Record<string, true> = {
  "frontend/src/routes/paths.ts": true,
  [TRANSPORT_OWNER]: true,
}

export default function checkFrontendApiLayer(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-api-layer", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendApiLayerSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-api-layer");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-api-layer",
      issues,
      "run make check-frontend-api-layer for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-api-layer") };
  }));
}
/**
 * A path literal whose first segment is one the backend actually routes.
 * Built from `backend/app/routers/*.py` so a new router is covered the day it
 * lands; the previous literal `(?:auth|user|batch|integration)` also silently
 * omitted `/health`, which the backend has always served.
 */
function urlLiteralPattern(): RegExp {
  const segments = [...routerPathSegments(projectRoot)].sort();
  return new RegExp(`['"\`]/(?:${segments.join("|")})[/'"\`]`);
}


export function checkFrontendApiLayerSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  issues.push(...checkTransportOwnership());
  issues.push(...checkUrlLiterals());
  issues.push(...checkServices());
  issues.push(...checkQueryHooks());
  issues.push(...checkScreensUseHooks());
  return issues;
}

/**
 * The AST rule proves no second axios instance exists; the string checks cover
 * `fetch` and the import, which are not one construct.
 */
function checkTransportOwnership(): string[] {
  const issues: string[] = [];
  const scanned = walkSources(frontendSrc).filter(
    (path: string) => label(path) !== TRANSPORT_OWNER,
  );
  if (scanned.length > 0) {
    const rulesDir = join(projectRoot, ".omp", "ast-grep", "rules", "frontend-api");
    issues.push(...runAstRules(rulesDir, scanned));
  }

  for (const file of readSources(frontendSrc)) {
    if (file.label === TRANSPORT_OWNER) continue;
    if (/\bfetch\s*\(/.test(file.content)) {
      issues.push(
        `${file.label}: raw fetch — call the api helpers from ${TRANSPORT_OWNER}, ` +
          "which attach the token and normalise the error",
      );
    }
    if (/^import .*from ['"]axios['"]/m.test(file.content) && !file.label.endsWith("errors.ts")) {
      issues.push(
        `${file.label}: imports axios — only ${TRANSPORT_OWNER} and its error mapper may`,
      );
    }
  }
  return issues;
}

function checkUrlLiterals(): string[] {
  const issues: string[] = [];
  const endpoints = join(SRC_DIRECTORIES.lib, "endpoints.ts");
  const urlLiteral = urlLiteralPattern();
  for (const file of readSources(frontendSrc)) {
    if (file.path === endpoints || URL_LITERAL_EXEMPT[file.label] === true) continue;
    file.content.split("\n").forEach((line: string, index: number) => {
      if (urlLiteral.test(line)) {
        issues.push(
          `${file.label}:${index + 1}: backend path literal — add it to ` +
            "frontend/src/lib/api/endpoints.ts so a renamed route fails a check",
        );
      }
    });
  }
  return issues;
}

/** A service that caches is a service no other caller can reuse. */
function checkServices(): string[] {
  const issues: string[] = [];
  for (const file of readSources(SRC_DIRECTORIES.services)) {
    if (/\buseQuery\b|\buseMutation\b/.test(file.content)) {
      issues.push(
        `${file.label}: a service must be transport only — move the caching to ` +
          "lib/api/hooks/",
      );
    }
    if (!/from ['"]@\/lib\/api\/client['"]/.test(file.content)) {
      issues.push(`${file.label}: does not import the shared client from @/lib/api/client`);
    }
  }
  return issues;
}

function checkQueryHooks(): string[] {
  const issues: string[] = [];
  for (const file of readSources(SRC_DIRECTORIES.queryHooks)) {
    for (const [hookName, body] of exportedFunctions(file.content)) {
      if (/useQuery\(/.test(body)) {
        if (/queryKey:\s*\[/.test(body)) {
          issues.push(
            `${file.label}: ${hookName} spells its own queryKey array — take it from ` +
              "the factory in lib/api/queryKeys.ts or no mutation can invalidate it",
          );
        }
        if (!/staleTime:\s*QUERY_STALE_TIME\./.test(body)) {
          issues.push(
            `${file.label}: ${hookName} sets no staleTime from QUERY_STALE_TIME — ` +
              "a bare number says how long, never why",
          );
        }
        if (/List\b/.test(hookName) && !/placeholderData:/.test(body)) {
          issues.push(
            `${file.label}: ${hookName} declares no placeholderData — usePagedRows ` +
              "needs the previous page to keep paginationMeta stable",
          );
        }
      }
      if (/useMutation\(/.test(body) && /^use(Create|Update|Delete)/.test(hookName)) {
        if (!/invalidateQueries\(/.test(body)) {
          issues.push(
            `${file.label}: ${hookName} does not invalidate its list key — the list ` +
              "keeps showing the row it just changed",
          );
        }
      }
    }
  }
  return issues;
}

function checkScreensUseHooks(): string[] {
  const issues: string[] = [];
  for (const root of [SRC_DIRECTORIES.sections, SRC_DIRECTORIES.pages]) {
    for (const file of readSources(root)) {
      if (/from ['"]@\/lib\/api\/services\//.test(file.content)) {
        issues.push(
          `${file.label}: imports a service directly — a screen goes through ` +
            "lib/api/hooks/ so the result is cached and invalidated with everything else",
        );
      }
    }
  }
  return issues;
}

/**
 * Splits a hooks module into `name → body`. A brace counter is enough here
 * because these modules are exported functions at the top level; it keeps the
 * per-hook checks from leaking across hook boundaries, which a whole-file regex
 * does (one compliant hook would excuse its neighbour).
 */
function exportedFunctions(content: string): Array<[string, string]> {
  const found: Array<[string, string]> = [];
  const pattern = /export function (\w+)\s*\(/g;
  let match = pattern.exec(content);
  while (match !== null) {
    const start = content.indexOf("{", match.index + match[0].length - 1);
    if (start !== -1) {
      let depth = 0;
      let end = start;
      for (let i = start; i < content.length; i += 1) {
        if (content[i] === "{") depth += 1;
        if (content[i] === "}") {
          depth -= 1;
          if (depth === 0) {
            end = i;
            break;
          }
        }
      }
      found.push([match[1], content.slice(start, end + 1)]);
    }
    match = pattern.exec(content);
  }
  return found;
}

// Direct execution (make check-frontend-api-layer): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-api-layer.ts")) {
  const issues = checkFrontendApiLayerSync();
  console.log("==> check-frontend-api-layer");
  if (issues.length === 0) {
    console.log("    PASS: frontend API layer contract valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-api-layer");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
