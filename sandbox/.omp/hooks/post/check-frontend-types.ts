import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import {
  SRC_DIRECTORIES,
  discoverDomains,
  frontendSrc,
  projectRoot,
  readIfPresent,
} from "../lib/frontend-source.ts";
import type { FieldType } from "../lib/frontend-types.ts";
import {
  expectedTsType,
  parseAliases,
  parsePydanticTypes,
  parseTsTypes,
} from "../lib/frontend-types.ts";
import { readBackendModule } from "../lib/frontend-contract.ts";
import { checkRequestContracts } from "../lib/frontend-request-contract.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * Check-Frontend-Types Post Hook
 *
 * Validates the typed half of the contract from .omp/rules/frontend-contract.md.
 * `check-frontend-contract` compares field *names*; this one compares what is in
 * the fields, and what a request may leave out:
 *
 *   1. request bodies — `<Domain>CreateRequest` / `<Domain>UpdateRequest` against
 *      the TS interfaces of the same name
 *   2. types — every annotation maps to exactly one TS type (`datetime` →
 *      `string`, `UUID` → `string`, `int` → `number`, `Literal[...]` → the same
 *      union, a nested model → its interface, `list[X]` → `X[]`)
 *   3. nullability — `X | None` in a response is `T | null` on the client, never
 *      a bare `T`
 *   4. optionality — a request field with a default is `field?:`, one without is
 *      required: "omitted" and "sent as null" mean different things to an
 *      update endpoint
 *   5. query parameters — a parameter the router reads exists in a params type
 *
 * Asymmetry on purpose: a **request** is what the client may send, so leaving
 * out an optional field is a choice; a **response** is what it will receive, so
 * a missing field is data the screen drops and an extra one is a lie.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

const RESPONSE_SUFFIX = "ReadResponse";

const REQUEST_SUFFIXES = ["CreateRequest", "UpdateRequest"];

/** `OffsetQuery = Annotated[int, Query(ge=0)]` — a router parameter typed with one. */
const QUERY_ALIAS = /^(\w+)\s*=\s*Annotated\[[^,]+,\s*Query\(/gm;

const ROUTER_QUERY_PARAM = /^ {4}(\w+):\s*(\w+)\s*=/;

export default function checkFrontendTypes(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-types", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendTypesSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-types");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-types",
      issues,
      "run make check-frontend-types for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-types") };
  }));
}

export function checkFrontendTypesSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  const sharedTs = readIfPresent(join(SRC_DIRECTORIES.types, "api.ts"));
  if (sharedTs === null) {
    return ["frontend/src/types/api.ts: missing — the shared wire types are the contract"];
  }

  for (const domain of discoverDomains()) {
    issues.push(...checkDomainTypes(domain, sharedTs));
  }
  issues.push(...checkQueryParams(sharedTs));
  issues.push(...checkRequestContracts(projectRoot, frontendSrc, SRC_DIRECTORIES.lib));
  return issues;
}

/** Every request and response model of one domain, field by field, type by type. */
function checkDomainTypes(domain: string, sharedTs: string): string[] {
  const issues: string[] = [];
  const backendSource = readBackendModule(projectRoot, "schemas", `${domain}.py`);
  const frontendSource = readIfPresent(join(SRC_DIRECTORIES.types, `${domain}.ts`));
  if (backendSource === null || frontendSource === null) return issues;

  // One parse over both files: `User extends AuditedResource` crosses the file
  // boundary, and resolving each file alone loses every inherited field.
  const combined = `${sharedTs}\n${frontendSource}`;
  const pyTypes = parsePydanticTypes(backendSource);
  const tsTypes = parseTsTypes(combined);
  const pyAliases = parseAliases(backendSource, "py");
  const tsAliases = parseAliases(combined, "ts");
  const label = `frontend/src/types/${domain}.ts`;

  for (const [model, fields] of pyTypes) {
    const target = modelToInterface(model);
    if (target === null) continue;
    const declared = tsTypes.get(target);
    if (declared === undefined) {
      // Every request model the server accepts, nested ones included: the
      // backend is the canonical shape, and a client that cannot express a
      // field the API takes is a gap nobody discovers until they need it.
      issues.push(`${label}: no interface ${target} — ${model} has no TypeScript counterpart`);
      continue;
    }
    const isResponse = model.endsWith(RESPONSE_SUFFIX);

    for (const [field, py] of fields) {
      const ts = declared.get(field);
      if (ts === undefined) {
        issues.push(`${label}: ${target} is missing ${field} — ${model} declares it`);
        continue;
      }
      issues.push(
        ...compareField({
          label,
          target,
          model,
          field,
          py,
          ts,
          isResponse,
          pyAliases,
          tsAliases,
        }),
      );
    }
    for (const field of declared.keys()) {
      if (!fields.has(field)) {
        issues.push(`${label}: ${target} declares ${field}, which ${model} does not`);
      }
    }
  }
  return issues;
}

/** One field: base type, nullability, and — for requests — optionality. */
function compareField(context: {
  label: string;
  target: string;
  model: string;
  field: string;
  py: FieldType;
  ts: FieldType;
  isResponse: boolean;
  pyAliases: Map<string, string>;
  tsAliases: Map<string, string>;
}): string[] {
  const { label, target, model, field, py, ts, isResponse, pyAliases, tsAliases } = context;
  const issues: string[] = [];
  const where = `${label}: ${target}.${field}`;

  const expected = expectedTsType(py.base, pyAliases, modelToInterface);
  if (expected === null) {
    issues.push(
      `${where}: cannot read the server annotation \`${py.base}\` — teach the parser or ` +
        "simplify the schema",
    );
  } else {
    const actual = tsAliases.get(ts.base) ?? ts.base;
    const wanted = tsAliases.get(expected) ?? expected;
    if (actual !== wanted) {
      issues.push(
        `${where} is \`${ts.base}\` but ${model}.${field} is \`${py.base}\` ` +
          `(expected \`${expected}\`)`,
      );
    }
  }

  if (isResponse) {
    // `unknown` already admits null, so demanding `| null` beside it would be
    // asking for a distinction TypeScript does not make.
    if (py.nullable && !ts.nullable && ts.base !== "unknown") {
      issues.push(
        `${where} is not nullable but ${model}.${field} is \`| None\` — the server sends null`,
      );
    }
    if (!py.nullable && ts.nullable) {
      issues.push(`${where} allows null, which ${model}.${field} never sends`);
    }
    if (ts.optional) {
      issues.push(`${where} is optional, but a response carries every field`);
    }
    return issues;
  }

  if (py.optional !== ts.optional) {
    issues.push(
      py.optional
        ? `${where} is required but ${model}.${field} has a default — an omitted field means ` +
            '"leave it alone"'
        : `${where} is optional but ${model}.${field} has no default — omitting it is a 422`,
    );
  }
  if (ts.nullable && !py.nullable) {
    issues.push(`${where} may send null, which ${model}.${field} rejects`);
  }
  return issues;
}


/** A query parameter the router reads must exist as a field of a params type. */
function checkQueryParams(sharedTs: string): string[] {
  const issues: string[] = [];
  const dependency = readBackendModule(projectRoot, "dependencies", "query.py");
  if (dependency === null) return issues;

  QUERY_ALIAS.lastIndex = 0;
  const aliases = new Set([...dependency.matchAll(QUERY_ALIAS)].map((match: string[]) => match[1]));
  if (aliases.size === 0) return issues;

  const declared = new Set<string>();
  for (const fields of parseTsTypes(sharedTs).values()) {
    for (const field of fields.keys()) declared.add(field);
  }
  for (const domain of discoverDomains()) {
    const routerSource = readBackendModule(projectRoot, "routers", `${domain}.py`);
    if (routerSource === null) continue;
    for (const line of routerSource.split("\n")) {
      const match = ROUTER_QUERY_PARAM.exec(line);
      if (match === null || !aliases.has(match[2])) continue;
      if (declared.has(match[1])) continue;
      issues.push(
        `frontend/src/types/api.ts: no ${match[1]} — backend/app/routers/${domain}.py reads it ` +
          "as a query parameter, so a call that omits it takes the server default silently",
      );
    }
  }
  return issues;
}



/** `UserReadResponse` → `User`; a request model keeps its own name. */
function modelToInterface(model: string): string | null {
  for (const suffix of [RESPONSE_SUFFIX, ...REQUEST_SUFFIXES]) {
    if (!model.endsWith(suffix)) continue;
    return suffix === RESPONSE_SUFFIX ? model.slice(0, -suffix.length) : model;
  }
  return null;
}

// Direct execution (make check-frontend-types): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-types.ts")) {
  const issues = checkFrontendTypesSync();
  console.log("==> check-frontend-types");
  if (issues.length === 0) {
    console.log("    PASS: request and response types match the backend, field for field");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-types");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
