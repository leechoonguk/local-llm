/**
 * What a request will actually do — checked before anyone sends it.
 *
 * The typed contract proves the *shapes* agree. These four prove the call cannot
 * fail on the way out or be misread on the way back, which is a different
 * question and the one that produces runtime failures:
 *
 * - **Response envelope** — the generic a service passes (`api.get<User[]>`)
 *   against the route's return annotation (`list[UserReadResponse]`). Getting
 *   this wrong is `.map is not a function` on a screen, with no type error
 *   anywhere, because the generic is an assertion about a value nobody checked.
 * - **Body encoding** — a handler reading `OAuth2PasswordRequestForm` / `Form(…)`
 *   must be called form-encoded. JSON to it is a 422 the login screen cannot
 *   explain, and the reverse wastes a round trip on a body the handler ignores.
 * - **Path arity** — an endpoint constant taking fewer arguments than the route
 *   has parameters builds a URL with `undefined` in it and answers 404.
 * - **Query bounds** — `Query(ge=…, le=…)` against the page sizes the UI offers.
 *   A page size above the cap is a guaranteed 422 the moment a user picks it,
 *   and no test covers a value only a dropdown can produce.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import type { RouteEntry } from "./frontend-routes.ts";
import { collectEndpointConstants, collectRoutes } from "./frontend-routes.ts";

interface ServiceCall {
  verb: string;
  key: string;
  generic: string;
  /** The body is `URLSearchParams`, which is what makes the request form-encoded. */
  form: boolean;
}

/** `api.get<User[]>(USER_ENDPOINTS.LIST, { params })` — verb, generic, endpoint key. */
const SERVICE_CALL = /api\.(get|post|put|patch|delete)<([^>]*)>\(\s*(\w+_ENDPOINTS\.\w+)([^\n]*)/g;

/** `DETAIL: (id: string) => …` — the arguments a caller must supply. */
const ENDPOINT_ARITY = /^ {2}(\w+):\s*(?:\(([^)]*)\)\s*=>)?/gm;

const PAGE_SIZE_OPTIONS = /export const PAGE_SIZE_OPTIONS = \[([^\]]*)\]/;

const NAMED_NUMBER = /export const (\w+) = (\d+)/g;

/** `LimitQuery = Annotated[int, Query(ge=1, le=100)]` — the server's own bounds. */
const QUERY_BOUND = /^(\w+)\s*=\s*Annotated\[[^,]+,\s*Query\(([^)]*)\)/gm;

/**
 * Pydantic return annotations and the only TypeScript generic that reads them.
 *
 * `dict[str, bool]` is the delete envelope (`{"ok": true}`, never 204), so the
 * client's `OkResponse` is the contract, not a convention.
 */
const RESPONSE_TYPES: Record<string, string> = {
  "dict[str, bool]": "OkResponse",
  "dict[str, str]": "Record<string, string>",
};

/**
 * An identity lookup serves its own answer or none.
 *
 * `placeholderData: (previous) => previous` is right for a *list*: the page
 * keeps its rows while the next page loads, and the reader sees the same table
 * for a moment longer. It is wrong for a read that answers **which row is
 * this** - a key lookup, a detail - because the previous answer is a different
 * row, and whatever the screen does with an id it now does to the wrong one.
 *
 * Measured: the 사건 list looked a product up by (종류, 번호) through
 * a list hook that kept the previous answer, so clicking a row opened the
 * dialog on the product of the *last* lookup - 886px of another company's
 * record - which collapsed to 303px and was replaced two frames later. One
 * blink, and a reader who read that frame read the wrong product.
 *
 * So a hook whose name or key says identity (`ByKey`, `ById`, `detail(`) must
 * be `enabled`-gated and carry no placeholder.
 */
function checkIdentityLookupsServeTheirOwnAnswer(frontendSrc: string): string[] {
  const issues: string[] = [];
  const hooksDir = join(frontendSrc, "lib", "api", "hooks");
  let files: string[];
  try {
    files = readdirSync(hooksDir);
  } catch {
    return issues;
  }
  for (const file of files) {
    if (!file.endsWith(".ts")) continue;
    const content = readFileSync(join(hooksDir, file), "utf-8");
    // Both spellings a hook is written in: a declaration and an arrow const.
    // A check that read only `export function` passed the same defect written
    // the other way, which is how a rule stops being a rule.
    const declared = content.matchAll(/export function (use\w+)\([^)]*\)[\s\S]*?useQuery\(\{([\s\S]*?)\n\s*\}\)/g);
    const arrows = content.matchAll(/export const (use\w+)\s*=\s*\([^)]*\)[^=]*=>[\s\S]*?useQuery\(\{([\s\S]*?)\}\)/g);
    for (const match of [...declared, ...arrows]) {
      const [, name, body] = match;
      // A detail key is not enough: a tab's own paged list is keyed under the
      // record it belongs to (`detail(`${id}:events`)`) and *is* a list - its
      // placeholder keeps the rows while the next page loads, which is right.
      // An identity read asks for one row and carries no window.
      const paged = /offset|limit|params/.test(body);
      const identity = /ById$|ByKey$/.test(name) || (/Keys\.detail\(/.test(body) && !paged);
      if (!identity) continue;
      if (/placeholderData/.test(body)) {
        issues.push(
          `src/lib/api/hooks/${file}: ${name} answers which row a key names but keeps the ` +
            "previous answer (placeholderData) - the screen then acts on another row until " +
            "this one arrives",
        );
      }
      if (!/enabled:/.test(body)) {
        issues.push(
          `src/lib/api/hooks/${file}: ${name} is an identity lookup with no enabled gate - it ` +
            "fetches a row nobody asked for and leaves it for the next key to inherit",
        );
      }
    }
  }
  return issues;
}


export function checkRequestContracts(
  projectRoot: string,
  frontendSrc: string,
  libDirectory: string,
): string[] {
  const issues: string[] = [];
  const endpointsSource = read(join(libDirectory, "endpoints.ts"));
  if (endpointsSource === null) return issues;

  const routes = new Map<string, RouteEntry>(
    collectRoutes(projectRoot).map((route: RouteEntry) => [route.signature, route]),
  );
  const constants = collectEndpointConstants(endpointsSource);
  const arity = parseEndpointArity(endpointsSource);
  const servicesDirectory = join(libDirectory, "services");

  for (const file of listServices(servicesDirectory)) {
    const source = readFileSync(join(servicesDirectory, file), "utf-8");
    const label = `frontend/src/lib/api/services/${file}`;
    for (const call of parseServiceCalls(source)) {
      const path = constants.get(call.key);
      if (path === undefined) continue;
      const route = routes.get(`${call.verb} ${path}`);
      if (route === undefined) continue;

      const expected = expectedGeneric(route.returns);
      if (expected !== null && call.generic !== expected) {
        issues.push(
          `${label}: ${call.verb} ${path} is read as \`${call.generic}\` but the route returns ` +
            `\`${route.returns}\` (expected \`${expected}\`)`,
        );
      }
      if (route.form && !call.form) {
        issues.push(
          `${label}: ${call.verb} ${path} sends JSON, but the handler reads a form body — ` +
            "send URLSearchParams with an urlencoded Content-Type or the server answers 422",
        );
      }
      if (!route.form && call.form) {
        issues.push(
          `${label}: ${call.verb} ${path} sends a form body the handler never reads`,
        );
      }

      const declared = arity.get(call.key) ?? 0;
      if (declared !== route.parameters) {
        issues.push(
          `frontend/src/lib/api/endpoints.ts: ${call.key} takes ${declared} argument(s) but ` +
            `${call.verb} ${path} declares ${route.parameters} path parameter(s) — the URL would ` +
            "carry undefined",
        );
      }
    }
  }

  issues.push(...checkPagingBounds(projectRoot, frontendSrc));
  issues.push(...checkIdentityLookupsServeTheirOwnAnswer(frontendSrc));
  return issues;
}

/** The page sizes the UI can send against the bounds the server declares. */
function checkPagingBounds(projectRoot: string, frontendSrc: string): string[] {
  const issues: string[] = [];
  const dependency = read(join(projectRoot, "backend", "app", "dependencies", "query.py"));
  const config = read(join(frontendSrc, "config.ts"));
  if (dependency === null || config === null) return issues;

  QUERY_BOUND.lastIndex = 0;
  const bounds = new Map<string, { ge?: number; le?: number }>();
  for (const match of dependency.matchAll(QUERY_BOUND)) {
    bounds.set(match[1], {
      ge: readBound(match[2], "ge"),
      le: readBound(match[2], "le"),
    });
  }
  const limit = bounds.get("LimitQuery");
  if (limit === undefined) return issues;

  NAMED_NUMBER.lastIndex = 0;
  const numbers = new Map<string, number>();
  for (const match of config.matchAll(NAMED_NUMBER)) numbers.set(match[1], Number(match[2]));

  const options = PAGE_SIZE_OPTIONS.exec(config)?.[1] ?? "";
  const sizes: { name: string; value: number }[] = [
    ...[...options.matchAll(/\d+/g)].map((match: string[]) => ({
      name: `PAGE_SIZE_OPTIONS ${match[0]}`,
      value: Number(match[0]),
    })),
    ...["DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE"]
      .filter((name: string) => numbers.has(name))
      .map((name: string) => ({ name, value: numbers.get(name)! })),
  ];

  for (const size of sizes) {
    if (limit.le !== undefined && size.value > limit.le) {
      issues.push(
        `frontend/src/config.ts: ${size.name} exceeds the server cap (LimitQuery le=${limit.le}) ` +
          "— choosing it answers 422",
      );
    }
    if (limit.ge !== undefined && size.value < limit.ge) {
      issues.push(
        `frontend/src/config.ts: ${size.name} is below the server minimum ` +
          `(LimitQuery ge=${limit.ge})`,
      );
    }
  }
  return issues;
}

function parseServiceCalls(source: string): ServiceCall[] {
  const calls: ServiceCall[] = [];
  SERVICE_CALL.lastIndex = 0;
  for (const match of source.matchAll(SERVICE_CALL)) {
    const rest = source.slice(match.index ?? 0, (match.index ?? 0) + 400);
    calls.push({
      verb: match[1].toUpperCase(),
      generic: match[2].trim(),
      key: match[3],
      // The body decides what axios sends: a plain object is JSON even with an
      // urlencoded header, so URLSearchParams is the claim, not the header.
      form: /URLSearchParams/.test(rest),
    });
  }
  return calls;
}

function parseEndpointArity(endpointsSource: string): Map<string, number> {
  const arity = new Map<string, number>();
  for (const block of endpointsSource.matchAll(
    /export const (\w+_ENDPOINTS) = \{([\s\S]*?)\n\} as const/g,
  )) {
    ENDPOINT_ARITY.lastIndex = 0;
    for (const entry of block[2].matchAll(ENDPOINT_ARITY)) {
      const parameters = entry[2] === undefined || entry[2].trim() === ""
        ? 0
        : entry[2].split(",").length;
      arity.set(`${block[1]}.${entry[1]}`, parameters);
    }
  }
  return arity;
}

/** The TypeScript generic one return annotation requires, or null when unknown. */
function expectedGeneric(returns: string): string | null {
  if (returns === "") return null;
  const mapped = RESPONSE_TYPES[returns];
  if (mapped !== undefined) return mapped;

  const list = /^list\[(.+)\]$/.exec(returns);
  if (list !== null) {
    const inner = expectedGeneric(list[1].trim());
    return inner === null ? null : `${inner}[]`;
  }
  const model = /^(\w+)ReadResponse$/.exec(returns);
  if (model !== null) return model[1];
  return /^\w+$/.test(returns) ? returns : null;
}

function readBound(arguments_: string, key: string): number | undefined {
  const match = new RegExp(`\\b${key}\\s*=\\s*(\\d+)`).exec(arguments_);
  return match === null ? undefined : Number(match[1]);
}

function listServices(directory: string): string[] {
  try {
    return readdirSync(directory).filter((file: string) => file.endsWith(".service.ts"));
  } catch {
    return [];
  }
}

function read(path: string): string | null {
  try {
    return readFileSync(path, "utf-8");
  } catch {
    return null;
  }
}
