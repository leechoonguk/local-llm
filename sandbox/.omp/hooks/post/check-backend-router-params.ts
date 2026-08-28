import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Backend-Router-Params Post Hook
 *
 * Validates the router parameter standard (backend-router-params.md) in
 * `backend/app/routers/`. Every parameter of an endpoint is one of four kinds,
 * and each kind has one spelling:
 *
 *   1. path parameter — declared in the route template, `UUID` for ids
 *   2. body — a single `*Request` schema named `data` (writes only)
 *   3. dependency — an `Annotated` alias ending in `Dep`
 *   4. query — an `Annotated` alias ending in `Query`, defined in
 *      `app/dependencies/query.py`, never an unbounded primitive
 *
 * The failures this prevents are all runtime-only: a path template that names a
 * parameter the signature does not (FastAPI silently turns it into a required
 * query parameter → 422 on every call), an unbounded `limit` (one request reads
 * the table), a `limit` default above the alias cap (422 on every unpaginated
 * call), and a body on GET/DELETE (proxies drop it).
 */

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
};

// ============================================================
// Constants
// ============================================================

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const routerDir = join(projectRoot, "backend", "app", "routers");
const queryModule = join(projectRoot, "backend", "app", "dependencies", "query.py");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

/**
 * `@router.<method>("<path>", …)`, any further decorators, then the signature.
 * The return annotation is captured because a list endpoint is defined by it.
 */
const ENDPOINT =
  /@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"[^)]*\)\s*\n(?:\s*@[^\n]+\n)*async def (\w+)\(([\s\S]*?)\)\s*->\s*([^\n:]+):/g;

const PATH_PARAM = /\{(\w+)\}/g;
const WRITE_METHODS: Record<string, true> = { post: true, put: true, patch: true };

/** Parameter kinds, in the order a signature must declare them. */
const KIND_RANK: Record<string, number> = { path: 0, body: 1, dependency: 2, query: 3 };
const KIND_ORDER_TEXT = "path → body → dependencies → query";

/**
 * The pagination contract, spelled once: parameter name, alias, and the only
 * default the standard accepts. `settings.items_per_user` keeps one page size
 * for the whole API, changeable per environment.
 */
const PAGINATION: Array<[string, string, string]> = [
  ["offset", "OffsetQuery", "0"],
  ["limit", "LimitQuery", "settings.items_per_user"],
];

interface Parameter {
  name: string;
  annotation: string;
  default: string | null;
  kind: string;
}

interface Endpoint {
  method: string;
  path: string;
  name: string;
  returns: string;
  parameters: Parameter[];
}

// ============================================================
// Functions
// ============================================================

export default function checkBackendRouterParams(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-router-params", event, () => {
    // Read-only tools never change files — running the check after them wastes context.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendRouterParamsSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-router-params");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-router-params",
      issues,
      "make check-backend-router-params",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-router-params") };
  }));
}

export function checkBackendRouterParamsSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(routerDir)) return issues;


  for (const file of readdirSync(routerDir).sort()) {
    if (!file.endsWith(".py") || file === "__init__.py") continue;
    const source = readFileSync(join(routerDir, file), "utf-8");

    if (/^\w+\s*(?::\s*\w+)?\s*=\s*Annotated\[/m.test(source)) {
      issues.push(
        `${file}: router declares its own Annotated alias — parameter aliases live in ` +
          "app/dependencies/ so every router spells the same parameter the same way",
      );
    }

    for (const endpoint of parseEndpoints(source)) {
      const label = `${file}:${endpoint.name}`;
      issues.push(...checkPathParams(label, endpoint));
      issues.push(...checkBody(label, endpoint));
      issues.push(...checkQuery(label, endpoint, source));
      issues.push(...checkOrder(label, endpoint));
    }
  }

  issues.push(...checkQueryAliases(readLimitCap()));
  return issues;
}

/** Path template ↔ signature, both ways, and id parameters typed `UUID`. */
function checkPathParams(label: string, endpoint: Endpoint): string[] {
  const issues: string[] = [];
  const declared = [...endpoint.path.matchAll(PATH_PARAM)].map((match) => match[1]);

  for (const name of declared) {
    const parameter = endpoint.parameters.find((candidate) => candidate.name === name);
    if (parameter === undefined) {
      issues.push(
        `${label}: route "${endpoint.path}" names {${name}} but the signature does not — ` +
          "FastAPI turns it into a required query parameter and every call answers 422",
      );
      continue;
    }
    if (name.endsWith("_id") && parameter.annotation !== "UUID") {
      issues.push(
        `${label}: path parameter ${name} is typed ${parameter.annotation} — ids are UUID, ` +
          "so a malformed id is a 422 at the boundary instead of a database error",
      );
    }
    if (parameter.default !== null) {
      issues.push(`${label}: path parameter ${name} has a default — a path segment is required`);
    }
  }
  return issues;
}

/** One `*Request` body named `data`, on write methods only. */
function checkBody(label: string, endpoint: Endpoint): string[] {
  const issues: string[] = [];
  const bodies = endpoint.parameters.filter((parameter) => parameter.kind === "body");

  if (bodies.length > 1) {
    issues.push(
      `${label}: ${bodies.length} body parameters — one request schema per endpoint, so the ` +
        "OpenAPI body is the schema, not an embedded object per parameter",
    );
  }
  for (const body of bodies) {
    if (body.name !== "data") {
      issues.push(`${label}: body parameter is named ${body.name} — the standard name is "data"`);
    }
  }
  if (!WRITE_METHODS[endpoint.method] && bodies.length > 0) {
    issues.push(
      `${label}: ${endpoint.method.toUpperCase()} takes a body — proxies and caches may drop it; ` +
        "move the input into the path or a query alias",
    );
  }
  if (WRITE_METHODS[endpoint.method] && bodies.length === 0) {
    const hasForm = endpoint.parameters.some((parameter) => /Form/.test(parameter.annotation));
    if (!hasForm) {
      issues.push(
        `${label}: ${endpoint.method.toUpperCase()} has no *Request body — a write endpoint takes ` +
          'a validated schema named "data" (or a form dependency)',
      );
    }
  }
  return issues;
}

/**
 * Every `list[...]` read is paginated the same way — no sub-collection
 * exemption. "The foreign key keeps it small" is an assumption about data, not a
 * bound in the code. The defaults are fixed too: one page size for the whole
 * API, taken from settings so an environment can change it.
 */
function checkQuery(label: string, endpoint: Endpoint, source: string): string[] {
  const issues: string[] = [];

  for (const parameter of endpoint.parameters) {
    if (parameter.kind !== "unclassified") continue;
    issues.push(
      `${label}: parameter ${parameter.name}: ${parameter.annotation} is neither a path ` +
        "parameter, a *Request body, a *Dep dependency nor a *Query alias — an unbounded " +
        "primitive parameter has no validation and no OpenAPI constraint",
    );
  }

  if (endpoint.method !== "get" || !endpoint.returns.trim().startsWith("list[")) return issues;

  for (const [name, alias, expected] of PAGINATION) {
    const parameter = endpoint.parameters.find((candidate) => candidate.name === name);
    if (parameter === undefined) {
      issues.push(
        `${label}: list read without ${name} — every endpoint returning list[...] is paginated ` +
          `(${name}: ${alias} = ${expected}), sub-collections included`,
      );
      continue;
    }
    if (parameter.annotation !== alias) {
      issues.push(
        `${label}: ${name} is typed ${parameter.annotation} — use the shared alias ${alias} ` +
          "so the bound is declared once",
      );
    }
    if (parameter.default !== expected) {
      issues.push(
        `${label}: ${name} defaults to ${parameter.default} — the standard default is ` +
          `${expected}; a literal is a second page size no environment can change`,
      );
    }
  }

  // Accepting pagination and not passing it on is worse than not accepting it:
  // the caller is told the page was applied.
  const body = endpointBody(source, endpoint);
  for (const [name] of PAGINATION) {
    if (body !== "" && !new RegExp(`\\b${name}\\b`).test(body)) {
      issues.push(
        `${label}: ${name} is accepted but never used in the handler — pass it to the service ` +
          "call so the page reaches the query",
      );
    }
  }
  return issues;
}

/** Signature order: what identifies the resource, then its input, then wiring. */
function checkOrder(label: string, endpoint: Endpoint): string[] {
  const issues: string[] = [];
  let highest = -1;
  let highestKind = "";
  for (const parameter of endpoint.parameters) {
    const rank = KIND_RANK[parameter.kind];
    if (rank === undefined) continue;
    if (rank < highest) {
      issues.push(
        `${label}: ${parameter.kind} parameter ${parameter.name} follows a ${highestKind} ` +
          `parameter — signatures run ${KIND_ORDER_TEXT}`,
      );
      continue;
    }
    highest = rank;
    highestKind = parameter.kind;
  }
  return issues;
}

/** The aliases themselves must carry the bounds every router relies on. */
function checkQueryAliases(limitCap: number | null): string[] {
  const issues: string[] = [];
  if (!existsSync(queryModule)) {
    issues.push(
      "dependencies/query.py is missing — pagination aliases (OffsetQuery, LimitQuery) are " +
        "declared once, not per router",
    );
    return issues;
  }
  const source = readFileSync(queryModule, "utf-8");
  const offset = /^OffsetQuery\s*=\s*Annotated\[int,\s*Query\(([^)]*)\)\]/m.exec(source);
  const limit = /^LimitQuery\s*=\s*Annotated\[int,\s*Query\(([^)]*)\)\]/m.exec(source);

  if (offset === null || !/\bge\s*=\s*0\b/.test(offset[1])) {
    issues.push("dependencies/query.py: OffsetQuery must be Annotated[int, Query(ge=0)]");
  }
  if (limit === null || !/\bge\s*=/.test(limit[1]) || limitCap === null) {
    issues.push(
      "dependencies/query.py: LimitQuery must declare both bounds — Query(ge=1, le=<cap>); " +
        "without le= one request can read the whole table",
    );
    return issues;
  }

  // A configured page size above the cap makes every unpaginated list call 422.
  for (const envFile of [join(projectRoot, ".env"), join(projectRoot, "backend", ".env")]) {
    if (!existsSync(envFile)) continue;
    const configured = /^ITEMS_PER_USER\s*=\s*(\d+)/m.exec(readFileSync(envFile, "utf-8"));
    if (configured === null) continue;
    if (Number(configured[1]) > limitCap) {
      issues.push(
        `${relative(envFile)}: ITEMS_PER_USER=${configured[1]} exceeds the LimitQuery cap ` +
          `(le=${limitCap}) — it is the default of every list endpoint, so each unpaginated ` +
          "call would answer 422",
      );
    }
  }
  return issues;
}

// ============================================================
// Helpers
// ============================================================

function parseEndpoints(source: string): Endpoint[] {
  const endpoints: Endpoint[] = [];
  for (const match of source.matchAll(ENDPOINT)) {
    const path = match[2];
    const pathNames = [...path.matchAll(PATH_PARAM)].map((name) => name[1]);
    endpoints.push({
      method: match[1],
      path,
      name: match[3],
      returns: match[5],
      parameters: splitParameters(match[4]).map((parameter) => classify(parameter, pathNames)),
    });
  }
  return endpoints;
}

/**
 * The handler's statements only. A multi-line signature closes on a
 * non-indented line (`) -> list[...]:`), so the body scan starts after that
 * line — starting at `def` stops the scan on the closing paren and reads nothing.
 */
function endpointBody(source: string, endpoint: Endpoint): string {
  const lines = source.split("\n");
  const start = lines.findIndex((line: string) =>
    new RegExp(`^async def ${endpoint.name}\\(`).test(line),
  );
  if (start === -1) return "";
  let signatureEnd = start;
  while (signatureEnd < lines.length && !/\)\s*->/.test(lines[signatureEnd])) signatureEnd += 1;
  let end = signatureEnd + 1;
  while (end < lines.length && (lines[end].trim() === "" || /^\s/.test(lines[end]))) end += 1;
  return lines.slice(signatureEnd + 1, end).join("\n");
}

/** `name: Annotation = default` — split at top-level commas only. */
function splitParameters(signature: string): Array<{ name: string; annotation: string; default: string | null }> {
  const parameters: Array<{ name: string; annotation: string; default: string | null }> = [];
  let current = "";
  let depth = 0;
  for (const character of `${signature},`) {
    if ("([{".includes(character)) depth += 1;
    if (")]}".includes(character)) depth -= 1;
    if (character === "," && depth === 0) {
      const parsed = /^(\w+)\s*:\s*([^=]+?)(?:\s*=\s*(.+))?$/.exec(current.trim());
      current = "";
      if (parsed === null) continue;
      parameters.push({
        name: parsed[1],
        annotation: parsed[2].trim(),
        default: parsed[3] === undefined ? null : parsed[3].trim(),
      });
      continue;
    }
    current += character;
  }
  return parameters;
}

function classify(
  parameter: { name: string; annotation: string; default: string | null },
  pathNames: string[],
): Parameter {
  const annotation = parameter.annotation;
  let kind = "unclassified";
  if (pathNames.includes(parameter.name)) kind = "path";
  else if (/Request$/.test(annotation)) kind = "body";
  else if (/Dep$/.test(annotation)) kind = "dependency";
  else if (/Query$/.test(annotation)) kind = "query";
  return { ...parameter, kind };
}

function readLimitCap(): number | null {
  if (!existsSync(queryModule)) return null;
  const cap = /^LimitQuery\s*=\s*Annotated\[int,\s*Query\([^)]*\ble\s*=\s*(\d+)/m.exec(
    readFileSync(queryModule, "utf-8"),
  );
  return cap === null ? null : Number(cap[1]);
}

function relative(path: string): string {
  return path.startsWith(projectRoot) ? path.slice(projectRoot.length + 1) : path;
}

// Direct execution (make check-backend-router-params): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-router-params.ts")) {
  const issues = checkBackendRouterParamsSync();
  console.log("==> check-backend-router-params");
  if (issues.length === 0) {
    console.log("    PASS: router parameter standard valid");
  } else {
    for (const issue of issues) {
      console.log(`    FAIL: ${issue}`);
    }
    printRuleHint("check-backend-router-params");
    console.log(`    ${issues.length} issue(s) found`);
    process.exit(1);
  }
}
