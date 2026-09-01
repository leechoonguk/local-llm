import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import {
  SRC_DIRECTORIES,
  discoverDomains,
  frontendSrc,
  pascalCase,
  projectRoot,
  readIfPresent,
} from "../lib/frontend-source.ts";
import type { FieldConstraints, TypeShape } from "../lib/frontend-contract.ts";
import {
  parsePydanticClasses,
  parsePydanticConstraints,
  parseTsInterfaces,
  parseServiceShapeRules,
  parseYupRules,
  readBackendModule,
  resolveFields,
} from "../lib/frontend-contract.ts";
import { buildUsageGraph } from "../lib/frontend-usage.ts";
import type { RouteEntry } from "../lib/frontend-routes.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import {
  collectEndpointConstants,
  collectRoutes,
  collectServiceCalls,
} from "../lib/frontend-routes.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-Contract Post Hook
 *
 * Compares the frontend's copy of the backend contract against the backend
 * itself (.omp/rules/frontend-contract.md):
 *
 *   1. `<Domain>ReadResponse` fields ↔ the domain's TypeScript interface, both
 *      ways — a field added on the server and missed here arrives undefined
 *   2. router route paths ↔ `endpoints.ts`, both ways — a renamed prefix is a
 *      404 nobody sees until the screen is opened
 *   3. `AuditMixin` columns ↔ `AuditedResource`
 *   4. the error body (`detail`, `code`, `request_id`) ↔ `ApiErrorBody`
 *
 * The frontend cannot import the backend's types, so this is the only thing
 * standing between a schema change and a runtime surprise.
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/** Keys the uniform error body always carries (`app/core/exceptions.py`). */
const ERROR_BODY_KEYS = ["detail", "code", "request_id"];

/**
 * Routes no browser calls, each with the reason it exists.
 *
 * A route here is not "unfinished" — it is finished and not for the app. Anything
 * else with no caller is a gap the check reports.
 */
const NOT_FROM_BROWSER: Record<string, string> = {
  "GET /health": "orchestrator liveness probe with a DB ping: a screen for it would prove nothing",
  "POST /integration/{}/secrets":
    "a credential is written by an operator through the .http files; the UI shows secrets " +
    "read-only on purpose, because a value that cannot be read back cannot be confirmed",
  "DELETE /integration/{}/secrets/{}":
    "same operator path as writing one — the screen would offer a destructive action with no " +
    "way to verify what it removed",
  "GET /integration/{}/secrets":
    "the detail response already embeds a provider's secrets, so this list route serves the " +
    ".http scenarios; a second read path in the UI would be two sources for one table",
};

export default function checkFrontendContract(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-contract", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendContractSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-contract");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-contract",
      issues,
      "run make check-frontend-contract for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-contract") };
  }));
}
/**
 * Fields `AuditedResource` must mirror: the audit mixin's own columns plus the
 * primary key.
 *
 * Read from `models/base.py`, because this list is a copy of something the
 * backend declares. Measured as a literal: adding a column to `AuditMixin`
 * left the TypeScript interface unchanged and nothing said so - every row would
 * carry a field no client knew about.
 */
function auditFields(): string[] {
  const base = readBackendModule(projectRoot, "models", "base.py");
  if (base === null) return ["id"];
  const mixin = /class AuditMixin[^\n]*:\n((?:[ \t].*\n|\n)*)/.exec(base);
  if (mixin === null) return ["id"];
  const columns = [...mixin[1].matchAll(/^ {4}(\w+):\s*Mapped\[/gm)].map((m) => m[1]);
  return ["id", ...columns];
}

export function checkFrontendContractSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  const apiTypes = readIfPresent(join(SRC_DIRECTORIES.types, "api.ts"));
  if (apiTypes === null) {
    return ["frontend/src/types/api.ts: missing — the shared wire types are the contract"];
  }
  const shared = parseTsInterfaces(apiTypes);

  issues.push(...checkAuditShape(shared));
  issues.push(...checkErrorShape(shared));

  issues.push(...checkRouteCoverage());

  for (const domain of discoverDomains()) {
    issues.push(...checkDomainFields(domain, shared));
    issues.push(...checkValidationParity(domain));
  }
  return issues;
}

function checkAuditShape(shared: Map<string, TypeShape>): string[] {
  const issues: string[] = [];
  const audited = shared.get("AuditedResource");
  if (audited === undefined) {
    return ["frontend/src/types/api.ts: no AuditedResource — every read model shares those columns"];
  }
  for (const field of auditFields()) {
    if (!audited.fields.includes(field)) {
      issues.push(
        `frontend/src/types/api.ts: AuditedResource is missing ${field} — the backend's ` +
          "AuditMixin sends it on every row",
      );
    }
  }
  return issues;
}

function checkErrorShape(shared: Map<string, TypeShape>): string[] {
  const issues: string[] = [];
  const body = shared.get("ApiErrorBody");
  if (body === undefined) {
    return ["frontend/src/types/api.ts: no ApiErrorBody — the uniform error body is untyped"];
  }
  for (const key of ERROR_BODY_KEYS) {
    if (!body.fields.includes(key)) {
      issues.push(
        `frontend/src/types/api.ts: ApiErrorBody is missing ${key} — every handler in ` +
          "app/core/exceptions.py returns it",
      );
    }
  }
  return issues;
}

/** The read response is the only shape the UI receives, so it is the one compared. */
function checkDomainFields(domain: string, shared: Map<string, { fields: string[] }>): string[] {
  const issues: string[] = [];
  const backendSource = readBackendModule(projectRoot, "schemas", `${domain}.py`);
  const frontendSource = readIfPresent(join(SRC_DIRECTORIES.types, `${domain}.ts`));
  if (backendSource === null || frontendSource === null) return issues;

  const name = pascalCase(domain);
  const pydantic = parsePydanticClasses(backendSource);
  const readModel = `${name}ReadResponse`;
  if (!pydantic.has(readModel)) return issues;

  const expected = resolveFields(readModel, pydantic);
  const interfaces = parseTsInterfaces(frontendSource);
  if (!interfaces.has(name)) {
    return [
      `frontend/src/types/${domain}.ts: no interface ${name} — ${readModel} has no ` +
        "TypeScript counterpart",
    ];
  }

  const merged = new Map([...shared, ...interfaces]);
  const actual = resolveFields(name, merged as Map<string, { name: string; bases: string[]; fields: string[] }>);

  for (const field of expected) {
    if (!actual.has(field)) {
      issues.push(
        `frontend/src/types/${domain}.ts: interface ${name} is missing ${field} — ` +
          `${readModel} sends it`,
      );
    }
  }
  for (const field of actual) {
    if (!expected.has(field)) {
      issues.push(
        `frontend/src/types/${domain}.ts: interface ${name} declares ${field}, which ` +
          `${readModel} never sends`,
      );
    }
  }
  return issues;
}

/**
 * Every route against every call, both directions, plus dead constants.
 *
 * A route is covered only when a screen can reach it: service function → query
 * hook → screen. Coverage used to stop at the transport layer, so the execute
 * route looked covered while the app had no operation feature at all — the
 * service function and the hook existed and nothing rendered them.
 *
 * `NOT_FROM_BROWSER` is the escape hatch, and it is deliberately a list of
 * sentences: a route reachable only by an orchestrator or an operator belongs
 * there *with its reason*, and an entry whose route no longer exists fails, so
 * the list cannot rot into a blanket exemption.
 */
function checkRouteCoverage(): string[] {
  const issues: string[] = [];
  const endpointsSource = readIfPresent(join(SRC_DIRECTORIES.lib, "endpoints.ts"));
  if (endpointsSource === null) {
    return ["frontend/src/lib/api/endpoints.ts: missing — the route registry is the contract"];
  }

  const usage = buildUsageGraph(frontendSrc);
  const routes = collectRoutes(projectRoot);
  const constants = collectEndpointConstants(endpointsSource);
  const { calls, usedKeys } = collectServiceCalls(
    join(SRC_DIRECTORIES.lib, "services"),
    constants,
    usage.reachable,
  );

  for (const [symbol, users] of usage.serviceUsers) {
    if (users.length > 0) continue;
    issues.push(
      `frontend/src/lib/api/services/: ${symbol} is used by nothing — a transport function no ` +
        "hook calls cannot reach a screen",
    );
  }
  for (const [hook, users] of usage.hookUsers) {
    if (users.length > 0) continue;
    issues.push(
      `frontend/src/lib/api/hooks/: ${hook} is rendered by nothing — a hook no screen uses is ` +
        "a feature that was never built",
    );
  }

  const exempt = new Set(Object.keys(NOT_FROM_BROWSER));
  for (const route of routes) {
    if (calls.has(route.signature) || exempt.has(route.signature)) continue;
    issues.push(
      `${route.source}: ${route.signature} has no frontend caller — either a screen is ` +
        "missing or the route should not be published (declare it in NOT_FROM_BROWSER with " +
        "its reason)",
    );
  }

  const served = new Set(routes.map((route: RouteEntry) => route.signature));
  for (const [signature, source] of calls) {
    if (served.has(signature)) continue;
    issues.push(`${source}: calls ${signature}, which no router serves — 404 or 405 at runtime`);
  }

  for (const signature of exempt) {
    if (!served.has(signature)) {
      issues.push(
        `.omp/hooks/post/check-frontend-contract.ts: NOT_FROM_BROWSER lists ${signature}, ` +
          "which no router serves — remove the exemption with the route",
      );
    }
  }

  for (const key of constants.keys()) {
    if (usedKeys.has(key)) continue;
    issues.push(
      `frontend/src/lib/api/endpoints.ts: ${key} is declared and never called — a constant ` +
        "nobody uses is what a half-built feature leaves behind",
    );
  }
  return issues;
}

/**
 * The form dialog's yup rules against what the server actually refuses.
 *
 * Every direction here is a bug that was measured in this repository:
 *
 * - **Client-only rule.** The user form demanded an email shape and an 8-char
 *   password while `UserCreateRequest` said `str`, so the API stored
 *   `not-an-email` with a one-character password and answered 201.
 * - **Invented rule.** The integration form demanded `^[a-z][a-z0-9_]*$` for
 *   `code`, which rejects `mfds-food-safety-korea` — the app's own seeded
 *   provider.
 * - **Missing rule.** The same form then had *no* pattern, so `BAD Code` and
 *   `http://…` passed the dialog and came back 422 from the service.
 *
 * The shape rules are not all in the schema: `IntegrationService` compiles
 * `CODE_PATTERN` and parses `base_url` itself. A check that reads only Pydantic
 * "proves" a parity that does not exist, so the service is read too.
 */
function checkValidationParity(domain: string): string[] {
  const issues: string[] = [];
  const backendSource = readBackendModule(projectRoot, "schemas", `${domain}.py`);
  if (backendSource === null) return issues;

  const name = pascalCase(domain);
  const dialogPath = join(SRC_DIRECTORIES.sections, domain, `${name}FormDialog.tsx`);
  const dialogSource = readIfPresent(dialogPath);
  if (dialogSource === null) return issues;

  const constraints = parsePydanticConstraints(backendSource).get(`${name}CreateRequest`);
  if (constraints === undefined) return issues;

  const rules = parseYupRules(dialogSource);
  const label = `frontend/src/sections/${domain}/${name}FormDialog.tsx`;

  const serviceSource = readBackendModule(projectRoot, "services", `${domain}.py`);
  const shaped = serviceSource === null ? new Set<string>() : parseServiceShapeRules(serviceSource);

  for (const [field, rule] of rules) {
    const declared: FieldConstraints | undefined = constraints.get(field);
    if (declared === undefined) continue;
    const serverShapes = declared.pattern || shaped.has(field);

    if (declared.max !== undefined && rule.max !== declared.max) {
      issues.push(
        `${label}: ${field} allows ${rule.max ?? "any"} characters but ` +
          `${name}CreateRequest caps it at ${declared.max} — the server answers 422 with no ` +
          "field named, so the form must say it first",
      );
    }
    if (declared.min !== undefined && declared.min > 1 && rule.min !== declared.min) {
      issues.push(
        `${label}: ${field} accepts ${rule.min ?? "any"} characters but ` +
          `${name}CreateRequest requires ${declared.min}`,
      );
    }
    if (rule.matches && !serverShapes) {
      issues.push(
        `${label}: ${field} enforces a character pattern neither ${name}CreateRequest nor ` +
          `app/services/${domain}.py declares — the form is rejecting input the API accepts`,
      );
    }
    if (!rule.matches && serverShapes) {
      const owner = declared.pattern
        ? `${name}CreateRequest`
        : `app/services/${domain}.py`;
      issues.push(
        `${label}: ${field} accepts any shape, but ${owner} validates one — the user ` +
          "learns it only from a 422",
      );
    }
  }
  return issues;
}

// Direct execution (make check-frontend-contract): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-contract.ts")) {
  const issues = checkFrontendContractSync();
  console.log("==> check-frontend-contract");
  if (issues.length === 0) {
    console.log("    PASS: frontend types and endpoints match the backend contract");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-contract");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
