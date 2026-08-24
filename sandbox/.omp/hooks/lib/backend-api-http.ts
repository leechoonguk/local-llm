// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import {
  listIntegrationCallerInputs,
  listIntegrationOperations,
  listIntegrationPathFields,
  listUnreadableOperationSeeds,
  PAGING_FAMILIES,
  PAGING_KEYS,
} from "./backend-migration-policy.ts";

/**
 * api/*.http standard (backend-api-http.md).
 *
 * An .http file must run top to bottom, repeatedly, against a freshly migrated
 * database without hand-editing an id. The checks below encode that:
 *
 *   - file ↔ router sync in both directions, and location (`api/`, not
 *     `backend/api/`)
 *   - structure: title, prerequisites, `@base`, named login block before the
 *     first authenticated request, sections numbered 1..n with the expected
 *     status in the title, Bearer on non-public requests
 *   - endpoint coverage: one request block per `@router.<method>`
 *   - no literal id in a request line — ids come from variables, and those
 *     declarations sit outside request blocks (REST Client would send them as body)
 *   - CRUD sequencing: create → list → get → update → [409] → delete → [404],
 *     with the created id chained from the named create block, and a dynamic
 *     value in the create body when the model declares uniqueness
 *   - external API coverage: an execute block per seeded integration operation
 *   - the runtime proof exists: `make check-api-flow` runs every file through
 *     `lib/backend-api-flow.ts` and compares row counts before and after
 *
 * Pure validation — no ast-grep, no side effects.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

/** Public endpoints that legitimately carry no Authorization header. */
const PUBLIC_REQUESTS = [
  { method: "POST", path: "/auth/login" },
  { method: "POST", path: "/user/" },
  { method: "GET", path: "/health" },
];

/**
 * The account the seed migration creates. The domain files send these two values
 * verbatim: a variable would only be one more thing the client can fail to
 * resolve, and when that happens the request answers 401 with no hint why
 * (measured).
 */
const SEEDED_ACTOR = { username: "api-actor", password: "api-actor-secret" };

/** Header prose continuations align under "순차 실행: " — three hashes plus 11 spaces. */
const HEADER_CONTINUATION_INDENT = 11;

/**
 * `@base` names one declared source instead of a literal host. REST Client
 * resolves `{{$dotenv NAME}}` from the `.env` sitting **next to the .http file**
 * (upstream README), so the pair lives in `api/`, and switching target hosts is
 * one line in `api/.env` instead of an edit in every file. A literal host was
 * the old rule, and it drifted: five files pointed at a public IP while the
 * check still demanded localhost.
 */
const BASE_VARIABLE = "API_ORIGIN";
const BASE_DECLARATION = `@base = {{$dotenv ${BASE_VARIABLE}}}/api/v1`;

/** An origin — scheme, host, the fixed API port. No path: `/health` sits above `/api/v1`. */
const BASE_VALUE = /^https?:\/\/[^\s/:]+:18000$/;

/** The five endpoints that make a router a CRUD router. */
const CRUD_ENDPOINTS = [
  { method: "POST", path: "/" },
  { method: "GET", path: "/" },
  { method: "GET", path: "/{id}" },
  { method: "PUT", path: "/{id}" },
  { method: "DELETE", path: "/{id}" },
];

interface HttpRequest {
  method: string;
  target: string;
  path: string;
  index: number;
}

interface HttpSection {
  number: number;
  title: string;
  index: number;
}

export function checkDomainApiHttp(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");
  const routerDir = join(base, "routers");
  const modelDir = join(base, "models");
  const apiDir = join(projectRoot, "api");
  if (!existsSync(routerDir) || !existsSync(apiDir)) return issues;

  // A router owns one primary file (`<router>.http`) and any number of
  // companions (`<router>.<slug>.http`). The router is the first dot-segment, so
  // the mapping needs no registry — and endpoint coverage reads the union,
  // because a block moved into a companion still covers its endpoint.
  const byRouter = new Map<string, { primary: string | null; companions: string[] }>();
  for (const file of readdirSync(apiDir)) {
    if (!file.endsWith(".http")) continue;
    const name = file.replace(/\.http$/, "");
    const router = name.split(".")[0];
    const entry = byRouter.get(router) ?? { primary: null, companions: [] };
    if (name === router) entry.primary = file;
    else entry.companions.push(file);
    byRouter.set(router, entry);
  }

  for (const file of readdirSync(routerDir)) {
    if (!file.endsWith(".py") || file === "__init__.py") continue;
    const name = file.replace(/\.py$/, "");
    const group = byRouter.get(name);
    if (group?.primary === undefined || group?.primary === null) {
      issues.push(
        `${name}: router exists but api/${name}.http is missing — ` +
          "every API router must have a matching .http test file",
      );
      continue;
    }

    const router = readFileSync(join(routerDir, file), "utf-8");
    const endpoints = parseEndpoints(router);
    const covering: HttpRequest[] = [];

    for (const httpFile of [group.primary, ...group.companions]) {
      const label = httpFile.replace(/\.http$/, "");
      const http = readFileSync(join(apiDir, httpFile), "utf-8");
      const requests = parseRequests(http);
      const sections = parseSections(http);
      covering.push(...requests);

      issues.push(...checkStructure(label, http, requests, sections));
      issues.push(...checkVariablePlacement(label, http));
      issues.push(...checkCommentLayout(label, http));
      issues.push(...checkAuthorization(label, http, requests, sections));
      issues.push(...checkLiteralIds(label, requests));
      issues.push(...checkStateNeutrality(label, requests, sections));
      issues.push(...checkActorLifecycle(label, http, requests, sections));
      // The CRUD sequence is the primary file's contract: a companion exercises
      // one endpoint, not the resource lifecycle.
      if (httpFile === group.primary && isCrudRouter(endpoints)) {
        issues.push(...checkCrudSequence(label, http, requests, sections, modelDir));
      }
    }

    issues.push(...checkEndpointCoverage(name, endpoints, covering));
  }

  // Reverse sync: every api/*.http must map to a router — the first dot-segment
  // is the router name, so a companion is anchored just like its primary.
  for (const [router, group] of byRouter) {
    if (existsSync(join(routerDir, `${router}.py`))) continue;
    for (const file of [group.primary, ...group.companions].filter((f) => f !== null)) {
      issues.push(
        `${file}: api test file exists but routers/${router}.py is missing — ` +
          "an .http file must test an existing router",
      );
    }
  }

  issues.push(...checkExternalApiCoverage(apiDir));

  issues.push(...checkBaseSource(apiDir));

  // Location standard: api/*.http lives in the repository-root api/ directory.
  // A backend/api/ copy is invisible to router sync and the content standard.
  const backendApiDir = join(projectRoot, "backend", "api");
  if (existsSync(backendApiDir)) {
    for (const file of readdirSync(backendApiDir)) {
      if (!file.endsWith(".http")) continue;
      issues.push(
        `${file}: .http file in backend/api/ is outside the api/*.http standard — ` +
          "move it to the repository-root api/ directory (backend-api-http.md)",
      );
    }
  }

  issues.push(...checkFlowProof());

  return issues;
}

/**
 * The declaration `@base` points at must exist and must be a base URL.
 *
 * `api/.env.example` is the committed reference and is required: it is the only
 * copy a fresh clone has, and `make verify` must pass there. `api/.env` is
 * gitignored local truth — checked for shape when present, never required, so
 * the gate stays hermetic.
 */
function checkBaseSource(apiDir: string): string[] {
  const issues: string[] = [];
  const examplePath = join(apiDir, ".env.example");
  if (!existsSync(examplePath)) {
    issues.push(
      `api/.env.example is missing — it declares ${BASE_VARIABLE}, the one place every ` +
        "api/*.http resolves its host from",
    );
    return issues;
  }
  for (const [label, path] of [
    ["api/.env.example", examplePath],
    ["api/.env", join(apiDir, ".env")],
  ] as const) {
    if (!existsSync(path)) continue;
    const value = readEnvValue(readFileSync(path, "utf-8"), BASE_VARIABLE);
    if (value === null) {
      issues.push(`${label}: missing ${BASE_VARIABLE} — api/*.http cannot resolve {{base}} without it`);
      continue;
    }
    if (!BASE_VALUE.test(value)) {
      issues.push(
        `${label}: ${BASE_VARIABLE} = "${value}" — must be scheme://host:18000/api/v1 ` +
          "(the port and prefix are fixed; only the host varies)",
      );
    }
  }
  issues.push(...checkEnvSourceUsage(apiDir, examplePath));
  return issues;
}

/**
 * The env source is a contract in both directions, not a free-form knob:
 *
 *   - every `{{$dotenv NAME}}` a request file uses must be declared in
 *     `api/.env.example`, or a fresh clone resolves nothing and the request is
 *     sent with the template text in it (401/404 that reads as a broken file);
 *   - every key the example declares must be used by a request file, or it is a
 *     knob nobody turns that the next reader has to reverse-engineer.
 *
 * What may live here follows from that: a value that varies per target and does
 * not exist in the repository's deterministic state. The seeded actor is the
 * counter-example — `57_seed_api_actor_user.py` creates it unconditionally, so a
 * variable could only disagree with the database, and the login body is checked
 * verbatim elsewhere in this file.
 */
function checkEnvSourceUsage(apiDir: string, examplePath: string): string[] {
  const issues: string[] = [];
  const declared = new Set(
    [...readFileSync(examplePath, "utf-8").matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=/gm)].map((m) => m[1]),
  );
  const used = new Map<string, string>();
  for (const file of readdirSync(apiDir)) {
    if (!file.endsWith(".http")) continue;
    const http = readFileSync(join(apiDir, file), "utf-8");
    for (const match of http.matchAll(/\{\{\$dotenv\s+([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g)) {
      used.set(match[1], file);
    }
  }
  for (const [name, file] of used) {
    if (declared.has(name)) continue;
    issues.push(
      `${file}: {{$dotenv ${name}}} is not declared in api/.env.example — a fresh clone ` +
        "resolves nothing and sends the template text as the value",
    );
  }
  for (const name of declared) {
    if (used.has(name)) continue;
    issues.push(
      `api/.env.example: ${name} is declared but no api/*.http uses it — an env source ` +
        "holds values the request files actually resolve, not spare knobs",
    );
  }
  return issues;
}

/** An aligned `KEY = value` assignment, comments and blank lines ignored. */
function readEnvValue(content: string, key: string): string | null {
  const match = new RegExp(`^\\s*${key}\\s*=\\s*(.+?)\\s*$`, "m").exec(content);
  return match === null ? null : match[1];
}

// ============================================================
// Parsing
// ============================================================

function parseRequests(http: string): HttpRequest[] {
  return [...http.matchAll(/^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)/gm)].map((m) => ({
    method: m[1],
    target: m[2],
    path: normalizeRequestPath(m[2]),
    index: m.index ?? 0,
  }));
}

function parseSections(http: string): HttpSection[] {
  return [...http.matchAll(/^###\s+(\d+)\.\s*(.*)$/gm)].map((m) => ({
    number: Number(m[1]),
    title: m[2],
    index: m.index ?? 0,
  }));
}

function parseEndpoints(router: string): Array<{ method: string; path: string }> {
  const prefixMatch = router.match(/prefix="([^"]*)"/);
  const prefix = prefixMatch === null ? "" : prefixMatch[1];
  return [...router.matchAll(/@router\.(get|post|put|patch|delete)\("([^"]*)"/g)].map((m) => ({
    method: m[1].toUpperCase(),
    path: `${prefix}${m[2]}`,
  }));
}

/** Reduces an .http request target to the router-relative path. */
function normalizeRequestPath(target: string): string {
  let path = target
    // A leading template is the target's origin, never a path segment: files
    // address `{{base}}/…` and the one endpoint above the version prefix
    // (`/health`) addresses `{{$dotenv API_ORIGIN}}/…`.
    .replace(/^\{\{[^}]*\}\}/, "")
    .replace(/^https?:\/\/[^/]+/, "")
    .split("?")[0];
  path = path.replace(/^\/api\/v1/, "");
  // A template variable stands for exactly one path segment.
  path = path.replace(/\{\{[^}]*\}\}/g, "x");
  return path.startsWith("/") ? path : `/${path}`;
}

function isCrudRouter(endpoints: Array<{ method: string; path: string }>): boolean {
  return CRUD_ENDPOINTS.every((crud) =>
    endpoints.some(
      (endpoint) =>
        endpoint.method === crud.method &&
        (crud.path === "/"
          ? /^\/[^/{]*\/?$/.test(endpoint.path)
          : /\{[^}]+\}\/?$/.test(endpoint.path)),
    ),
  );
}


/**
 * Comments and alignment (backend-api-http.md "Comments and Alignment").
 *
 * `###` is a **delimiter**, not a comment marker: every `###` line starts a new
 * section in REST Client, so a narrative line written with three hashes silently
 * splits a block — the same class of defect as a `@var` inside a body, which
 * answered 422. Narrative belongs to `#`.
 *
 * The rest is alignment: a reader scans these files top-down, and drift in the
 * header shape costs more than it saves.
 */
function checkCommentLayout(name: string, http: string): string[] {
  const issues: string[] = [];
  const lines = http.split("\n");
  const firstSection = lines.findIndex((line: string) => /^### \d+\./.test(line));

  lines.forEach((line, index) => {
    const at = `${name}.http:${index + 1}`;

    // 1. `###` only for the title, the two header labels, their continuations,
    //    and numbered sections.
    if (
      index > 0 &&
      /^###/.test(line) &&
      !/^### \d+\. /.test(line) &&
      !/^### (전제|순차 실행):/.test(line) &&
      !/^###\s{2,}\S/.test(line)
    ) {
      issues.push(
        `${at}: "${line.slice(0, 48)}" uses ### for a comment — ### starts a new section in ` +
          "REST Client, so this line splits the block. Narrative lines use #",
      );
    }

    // 2. Header prose continuations align under "순차 실행: " (### + 11 spaces).
    const continuation = /^###(\s{2,})\S/.exec(line);
    if (continuation !== null && continuation[1].length !== HEADER_CONTINUATION_INDENT) {
      issues.push(
        `${at}: continuation line is indented ${continuation[1].length} spaces — the header ` +
          `prose aligns at ${HEADER_CONTINUATION_INDENT} (under "순차 실행: ")`,
      );
    }

    // 3. Every numbered section states a status and why it is expected.
    const section = /^### (\d+)\. (.+)$/.exec(line);
    if (section !== null && !/\(.+\)/.test(section[2])) {
      issues.push(
        `${at}: section "${section[2].slice(0, 40)}" has no "(...)" rationale — the title says ` +
          "what the block expects; the parenthetical says why",
      );
    }

    // 4. Variables: explained, aligned, and in the header.
    const variable = /^@([\w-]+)\s*=\s*(.*)$/.exec(line);
    if (variable !== null) {
      if (!/^@[\w-]+ = \S/.test(line)) {
        issues.push(`${at}: "${line.trim()}" — variables are written "@name = value"`);
      }
      if (variable[1] !== "base" && !/^#(?!##)/.test(lines[index - 1] ?? "")) {
        issues.push(
          `${at}: @${variable[1]} has no "#" comment above it — a variable without a stated ` +
            "reason is a magic value",
        );
      }
      if (firstSection !== -1 && index > firstSection) {
        issues.push(
          `${at}: @${variable[1]} is declared after the first numbered section — every ` +
            "variable belongs to the header block",
        );
      }
    }

    // 5. Whitespace hygiene: bodies indent with two spaces, never tabs.
    if (/\s$/.test(line)) issues.push(`${at}: trailing whitespace`);
    if (line.includes("\t")) issues.push(`${at}: tab indentation — bodies indent with 2 spaces`);
  });

  if (!http.endsWith("\n") || http.endsWith("\n\n")) {
    issues.push(`${name}.http: file must end with exactly one newline`);
  }
  return issues;
}

/**
 * A `@var = ...` declaration after a request body is sent **as part of that
 * body**: REST Client ends a body at the next `###` delimiter and nothing else.
 * The result is trailing JSON — measured as
 * `422 json_invalid / "Extra data"` at the exact offset of the `@`.
 *
 * The runner alone could not catch this: its parser used to treat `@var` as a
 * body boundary, so it was more forgiving than the client it emulates. This
 * check is the static half of that lesson.
 */
function checkVariablePlacement(name: string, http: string): string[] {
  const issues: string[] = [];
  const lines = http.split("\n");
  let requestSeen = false;
  lines.forEach((line, index) => {
    if (line.startsWith("###")) {
      requestSeen = false;
      return;
    }
    if (/^(GET|POST|PUT|PATCH|DELETE)\s+\S+/.test(line)) {
      requestSeen = true;
      return;
    }
    if (requestSeen && /^@[\w-]+\s*=/.test(line)) {
      issues.push(
        `${name}.http:${index + 1}: "${line.trim()}" sits inside a request block — REST Client ` +
          "sends everything up to the next ### as the body, so this line is appended to the " +
          "JSON and the request answers 422 (json_invalid: Extra data). Declare it before the " +
          "first request instead",
      );
    }
  });
  return issues;
}

// ============================================================
// Checks
// ============================================================

function checkStructure(
  name: string,
  http: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  const lines = http.split("\n");

  // A bare "###" is not a title: dropping line 1 promoted the 전제 comment and
  // the old check passed. The title names the API the file exercises.
  if (!/^###\s+.*\bAPI\b/.test(lines[0] ?? "")) {
    issues.push(`${name}.http: line 1 must be a "### <Name> API" title comment`);
  }
  if (!/^###\s*전제/m.test(http)) {
    issues.push(`${name}.http: missing "### 전제:" prerequisite comment`);
  }
  if (!http.includes(BASE_DECLARATION)) {
    issues.push(
      `${name}.http: missing "${BASE_DECLARATION}" — the target host is declared once in ` +
        `api/.env (${BASE_VARIABLE}), never written into a request file`,
    );
  }
  // A request line that spells out the host bypasses the declaration entirely:
  // endpoint coverage still matched (the path normaliser strips `/api/v1` either
  // way), so five files could point at one server and one at another with every
  // check green. `{{base}}` is the only way to name the target.
  for (const request of requests) {
    if (!/^https?:\/\//.test(request.target)) continue;
    issues.push(
      `${name}.http: ${request.method} ${request.target} spells out the host — ` +
        `address it as {{base}}/… so the target stays declared in api/.env (${BASE_VARIABLE})`,
    );
  }

  // The login block is only meaningful when something needs a token: requiring
  // it in a purely public file (health readiness) would be noise.
  const authenticatedRequests = requests.filter((request) => !isPublicRequest(request));
  const loginNameIndex = http.indexOf("# @name login");
  if (authenticatedRequests.length > 0) {
    if (loginNameIndex === -1 || !/POST\s+\{\{base\}\}\/auth\/login/.test(http)) {
      issues.push(
        `${name}.http: missing login block (# @name login + POST {{base}}/auth/login) — ` +
          "required for token auto-injection",
      );
    } else {
      // A token is only available after the login block has run.
      const firstAuthenticated = http.indexOf("Authorization: Bearer");
      if (firstAuthenticated !== -1 && firstAuthenticated < loginNameIndex) {
        issues.push(
          `${name}.http: an authenticated request precedes the login block — ` +
            "the token is undefined until login has run",
        );
      }
    }
  }

  // Sections numbered 1..n, one section per request block.
  if (sections.length === 0) {
    issues.push(`${name}.http: request blocks must open with "### N. <title>" sections`);
  } else {
    sections.forEach((section, position) => {
      if (section.number !== position + 1) {
        issues.push(
          `${name}.http: section "${section.number}. ${section.title}" is out of sequence — ` +
            `expected ${position + 1} (sections are numbered 1..n in run order)`,
        );
      }
      if (declaredStatus(section.title) === null) {
        issues.push(
          `${name}.http: section "${section.number}. ${section.title}" does not state its ` +
            "expected status code in the title",
        );
      }
    });
    if (sections.length !== requests.length) {
      issues.push(
        `${name}.http: ${requests.length} request(s) but ${sections.length} numbered ` +
          "section(s) — every request block needs exactly one section header",
      );
    }
  }
  return issues;
}

function checkAuthorization(
  name: string,
  http: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  for (const { request, body } of splitBlocks(http, requests)) {
    if (isPublicRequest(request)) continue;
    // A 401 case proves the endpoint rejects a missing token, so it omits the
    // header on purpose. The section title is what declares that intent.
    if (declaredStatus(sectionTitleFor(sections, request)) === "401") continue;
    if (!/Authorization: Bearer \{\{login\.response\.body\.access_token\}\}/.test(body)) {
      issues.push(
        `${name}.http: ${request.method} ${request.target} carries no ` +
          "Authorization: Bearer {{login.response.body.access_token}} header",
      );
    }
  }
  return issues;
}

function checkEndpointCoverage(
  name: string,
  endpoints: Array<{ method: string; path: string }>,
  requests: HttpRequest[],
): string[] {
  const issues: string[] = [];
  for (const endpoint of endpoints) {
    const pattern = new RegExp(
      "^" +
        endpoint.path
          .replace(/[.*+?^$()|[\]\\]/g, "\\$&")
          .replace(/\{[^}]*\}/g, "[^/]+")
          .replace(/\/$/, "/?") +
        "$",
    );
    if (!requests.some((request) => request.method === endpoint.method && pattern.test(request.path))) {
      issues.push(
        `${name}.http: no request block for ${endpoint.method} ${endpoint.path} — ` +
          "every router endpoint needs a matching .http request",
      );
    }
  }
  return issues;
}

/**
 * A literal UUID in a request line is the defect this standard removes: it makes
 * GET/PUT/DELETE answer 404 on every run and forces a manual paste.
 */
function checkLiteralIds(name: string, requests: HttpRequest[]): string[] {
  const issues: string[] = [];
  const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  for (const request of requests) {
    if (uuid.test(request.target)) {
      issues.push(
        `${name}.http: ${request.method} ${request.target} hardcodes a UUID — ` +
          "chain it from a named block or declare it as a variable at the top",
      );
    }
  }
  return issues;
}

function checkCrudSequence(
  name: string,
  http: string,
  requests: HttpRequest[],
  sections: HttpSection[],
  modelDir: string,
): string[] {
  const issues: string[] = [];
  const collection = new RegExp(`^/${name}/?$`);
  const item = new RegExp(`^/${name}/[^/]+$`);

  // The sequence's create is the *named* block the file chains its id from. A
  // file may hold other POSTs to the collection — a documented prerequisite, a
  // 409 duplicate, a 422 case — and those are not the sequence create.
  const named = new RegExp(`#\\s*@name\\s+create${capitalize(name)}\\b`).exec(http);
  const namedIndex = named === null ? -1 : (named.index ?? -1);
  const create = requests.find(
    (r) => r.method === "POST" && collection.test(r.path) && r.index > namedIndex,
  );
  const list = requests.find((r) => r.method === "GET" && collection.test(r.path));
  const get = requests.find((r) => r.method === "GET" && item.test(r.path));
  const update = requests.find((r) => r.method === "PUT" && item.test(r.path));
  const remove = requests.find((r) => r.method === "DELETE" && item.test(r.path));
  if (create === undefined || list === undefined || get === undefined || update === undefined || remove === undefined) {
    // Endpoint coverage already reports the missing block; ordering is moot.
    return issues;
  }

  // Run order: each step's precondition is produced by an earlier step.
  const order: Array<[string, HttpRequest]> = [
    ["create", create],
    ["list", list],
    ["get", get],
    ["update", update],
    ["delete", remove],
  ];
  for (let i = 1; i < order.length; i++) {
    if (order[i][1].index < order[i - 1][1].index) {
      issues.push(
        `${name}.http: ${order[i][0]} precedes ${order[i - 1][0]} — the runnable order is ` +
          "create → list → get → update → delete",
      );
    }
  }

  // The id must be chained from *this domain's* create block. A file may declare
  // other chained ids (the actor account it provisions), so matching the first
  // `@...Id =` line would compare against the wrong resource.
  const chainedName = `create${capitalize(name)}`;
  const idVariable = new RegExp(
    `^@(\\w*[Ii]d)\\s*=\\s*\\{\\{\\s*${chainedName}\\.response\\.body\\.id\\s*\\}\\}`,
    "m",
  ).exec(http);
  if (named === null) {
    issues.push(
      `${name}.http: the create block must be named "# @name create${capitalize(name)}" ` +
        "so its id can be chained",
    );
  }
  if (idVariable === null) {
    issues.push(
      `${name}.http: missing "@${name}Id = {{${chainedName}.response.body.id}}" — ` +
        "get/update/delete must address the id the file just created",
    );
  } else {
    const variable = `{{${idVariable[1]}}}`;
    for (const [label, request] of [["get", get], ["update", update], ["delete", remove]] as const) {
      if (!request.target.includes(variable)) {
        issues.push(
          `${name}.http: ${label} does not address ${variable} — ` +
            "it must operate on the resource created by step 1",
        );
      }
    }
  }

  // A 409 needs the resource alive; a 404 needs it gone.
  for (const section of sections) {
    if (declaredStatus(section.title) === "409" && section.index > remove.index) {
      issues.push(
        `${name}.http: conflict section "${section.title}" runs after the delete — ` +
          "a 409 case needs the created resource alive",
      );
    }
    if (declaredStatus(section.title) === "404" && section.index < remove.index) {
      issues.push(
        `${name}.http: not-found section "${section.title}" runs before the delete — ` +
          "a 404 case needs the resource gone",
      );
    }
  }

  // Required failure coverage.
  for (const code of ["404", "422", "401"]) {
    if (!sections.some((section) => declaredStatus(section.title) === code)) {
      issues.push(`${name}.http: no section covering ${code}`);
    }
  }

  // A unique constraint turns a static create body into a second-run 409 — and
  // `{{$timestamp}}` only moves the collision to "within the same second",
  // which is how a re-run from an editor fails (measured: 201 then 409).
  const modelPath = join(modelDir, `${name}.py`);
  if (existsSync(modelPath)) {
    const model = readFileSync(modelPath, "utf-8");
    const uniqueColumns = listUniqueColumns(model);
    if (uniqueColumns.length > 0) {
      const body = blockBody(http, create, requests);
      // Every unique column, not just one of them: a guid email next to a static
      // username still collides on the username (this check missed exactly that).
      for (const column of uniqueColumns) {
        const field = new RegExp(`"${column}"\\s*:\\s*"([^"]*)"`).exec(body);
        if (field === null) continue;
        if (!field[1].includes("{{$guid}}")) {
          issues.push(
            `${name}.http: "${column}": "${field[1]}" carries no {{$guid}} — ${column} is ` +
              "unique, so a static value 409s on the second run and {{$timestamp}} 409s on a " +
              "second run inside the same second",
          );
        }
      }
      // A uniqueness constraint is a reachable failure mode, so the file must
      // exercise it — and it needs the created row alive, hence before delete.
      if (!sections.some((section) => declaredStatus(section.title) === "409")) {
        issues.push(
          `${name}.http: no section covering 409 — ${name} declares a uniqueness ` +
            "constraint, so the duplicate case is part of its contract",
        );
      }
    }
  }
  return issues;
}

/**
 * Every external operation gets its **own** request file: `integration.<code>.http`.
 *
 * One file per operation, because a provider grows operations and a single file
 * turns into a pile where nobody can tell which blocks belong to which external
 * API. The name is the operation code, so the mapping needs no registry: adding
 * an integration without adding its file fails here.
 *
 * The file must carry an execute block for its own code with a **declared
 * status**, and the runner (`make check-api-flow`) proves that status against
 * the live stack. That split is deliberate: whether an operation can succeed
 * depends on rows this check cannot see (fields, secrets), so the file states
 * what the integration currently does and the runner refuses to let that
 * statement rot. An operation seeded without its configuration therefore
 * declares its 422 here and starts failing the runner the day the seed is
 * completed.
 */
function checkExternalApiCoverage(apiDir: string): string[] {
  const issues: string[] = [];
  for (const unreadable of listUnreadableOperationSeeds()) {
    issues.push(
      `${unreadable} — an operation this module cannot read is an integration nothing forces a ` +
        'request file for; seed rows as op.bulk_insert(<table var>, [ … "code": "…" … ])',
    );
  }
  for (const operation of listIntegrationOperations()) {
    const code = operation.code;
    const file = `integration.${code}.http`;
    const path = join(apiDir, file);
    if (!existsSync(path)) {
      issues.push(
        `api/${file} is missing — external operation '${code}' is seeded by a migration, ` +
          "and every integrated external API owns one request file named after its code",
      );
      continue;
    }
    const http = readFileSync(path, "utf-8");
    const requests = parseRequests(http);
    const sections = parseSections(http);
    const execute = requests.find(
      (request) => request.method === "POST" && request.target.includes(`/operations/${code}/execute`),
    );
    if (execute === undefined) {
      issues.push(
        `${file}: no execute block for '${code}' — the file named after an operation must call it`,
      );
      continue;
    }
    const status = declaredStatus(sectionTitleFor(sections, execute));
    if (status === null) {
      issues.push(
        `${file}: the '${code}' execute block declares no status in its section title — ` +
          "the runner compares against that number",
      );
    } else if (operation.configured && status !== "200") {
      issues.push(
        `${file}: the '${code}' execute block declares ${status}, but the migrations seed ` +
          `integration_field rows for it — a configured integration must prove its success path`,
      );
    } else if (!operation.configured && status === "200") {
      issues.push(
        `${file}: the '${code}' execute block declares 200, but no migration seeds ` +
          "integration_field rows for it — without them the path template cannot be resolved " +
          "and the call answers 422; finish the seed or declare what it really returns",
      );
    }
    if (!/"inputs"/.test(blockBody(http, execute, requests))) {
      issues.push(
        `${file}: the '${code}' execute block sends no "inputs" body — ` +
          "caller-sourced request fields are supplied through inputs",
      );
    }
    // Only a 200 block proves an input works, and only if it is the **one** filter
    // that block sends. A kitchen-sink call proves nothing about any single field:
    // measured, seven CALLER filters combined match no record, so the answer is an
    // empty page — a 200 that would otherwise cover all seven at once. Paging keys
    // are exempt: every block states the window, and their own blocks move it.
    const proven = new Set<string>();
    for (const request of requests) {
      if (!request.target.includes(`/operations/${code}/execute`)) continue;
      if (declaredStatus(sectionTitleFor(sections, request)) !== "200") continue;
      const keys = [...blockBody(http, request, requests).matchAll(/"([a-z0-9_]+)":/g)].map((m) => m[1]);
      const filters = keys.filter((key) => key !== "inputs" && !PAGING_KEYS.includes(key));
      for (const key of PAGING_KEYS.filter((key) => keys.includes(key))) proven.add(key);
      if (filters.length === 1) proven.add(filters[0]);
    }
    const missing = (listIntegrationCallerInputs().get(code) ?? []).filter((key) => !proven.has(key));
    if (missing.length > 0) {
      issues.push(
        `${file}: seeded CALLER input(s) with no success-path block: ${missing.join(", ")} — ` +
          "a request field the file never sends in a 200 call is a wire mapping that has " +
          "never been proven",
      );
    }
    issues.push(...checkPagingContract(file, code, http, requests, sections));
  }
  return issues;
}

/**
 * Paging is declared by the operation's REQUEST rows, and proven by its request
 * file.
 *
 * The seed side is the pattern itself: a paging operation maps a page, so its
 * `response_root` must name that page and must never pin an index — `/body/items/0`
 * returned one record however large the page was, which made the page-size input
 * unobservable (measured).
 *
 * The file side is what a reader can check without the database: a paging operation
 * must show the window moving **and** show what happens when the caller says
 * nothing, because "required, no default" is a claim until a 422 block proves it. A
 * non-paging operation must not pretend to page.
 */
function checkPagingContract(
  file: string,
  code: string,
  http: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  const operation = listIntegrationOperations().find((entry) => entry.code === code);
  const root = operation?.root ?? null;
  // A placeholder with no PATH field is unresolvable at call time: the client raises
  // "Request path variables are unresolved" and the operation answers 502 for every
  // caller. Measured on a seed whose template ended in `/{filters}` while the filters
  // were PATH_QUERY rows that append their own segment.
  const template = operation?.pathTemplate ?? null;
  if (template !== null) {
    const declared = new Set(listIntegrationPathFields().get(code) ?? []);
    const unfilled = [...template.matchAll(/\{([^}]+)\}/g)]
      .map((match) => match[1])
      .filter((name) => !declared.has(name));
    if (unfilled.length > 0) {
      issues.push(
        `${file}: operation '${code}' seeds path_template placeholder(s) ${unfilled.join(", ")} ` +
          "that no PATH field fills — the request path cannot be resolved, so every call answers 502",
      );
    }
  }
  if (root !== null && /\/\d+$/.test(root)) {
    issues.push(
      `${file}: operation '${code}' seeds response_root ${root}, which pins one record out ` +
        "of the page — the rows are resolved against each element, so the pointer names the page",
    );
  }
  const inputs = listIntegrationCallerInputs().get(code) ?? [];
  const declared = PAGING_KEYS.filter((key) => inputs.includes(key));
  if (declared.length === 0) {
    for (const request of requests) {
      if (!request.target.includes(`/operations/${code}/execute`)) continue;
      const body = blockBody(http, request, requests);
      const sent = PAGING_KEYS.filter((key) => new RegExp(`"${key}"\\s*:`).test(body));
      if (sent.length > 0) {
        issues.push(
          `${file}: sends paging input(s) ${sent.join(", ")} but the operation seeds none — ` +
            "an input no field row declares is dropped in silence",
        );
      }
    }
    return issues;
  }
  const family = Object.entries(PAGING_FAMILIES).find(
    ([, members]) => members.length === declared.length && members.every((key) => declared.includes(key)),
  );
  if (family === undefined) {
    issues.push(
      `${file}: operation '${code}' declares paging key(s) ${declared.join(", ")}, which is not ` +
        `one whole family — a window is a position and a size from the same family ` +
        `(${Object.keys(PAGING_FAMILIES).join(", ")})`,
    );
    return issues;
  }
  const familyKeys = family[1];
  if (root === null) {
    issues.push(
      `${file}: operation '${code}' declares paging inputs but seeds no response_root — ` +
        "a paging operation maps a page, and a page it does not name it cannot return",
    );
    return issues;
  }
  const omitted = requests.find((request) => {
    if (!request.target.includes(`/operations/${code}/execute`)) return false;
    if (declaredStatus(sectionTitleFor(sections, request)) !== "422") return false;
    const body = blockBody(http, request, requests);
    return familyKeys.every((key) => !new RegExp(`"${key}"\\s*:`).test(body));
  });
  if (omitted === undefined) {
    issues.push(
      `${file}: no 422 block that omits ${familyKeys.join(" and ")} — paging is required with ` +
        "no default, and that is a claim until a block proves the call is refused",
    );
  }
  return issues;
}

/**
 * Running every .http file must leave the database as `make db-init` left it.
 * Two ways a file breaks that, both checkable:
 *
 *   1. it creates a row it never deletes — a successful create (`— 201`) with no
 *      matching successful delete (`— 200`) on that collection's item path;
 *   2. it deletes a **seeded** row — a successful delete addressing an id that
 *      the file declares as a literal UUID (a seed migration's fixed id).
 *
 * A child created inside its parent's payload needs no delete of its own: the
 * parent's delete removes it by cascade.
 */
function checkStateNeutrality(
  name: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  const created = new Map<string, number>();
  const deleted = new Map<string, number>();

  for (const request of requests) {
    const status = declaredStatus(sectionTitleFor(sections, request));
    if (request.method === "POST" && status === "201") {
      const collection = request.path.replace(/\/$/, "");
      created.set(collection, (created.get(collection) ?? 0) + 1);
    }
    if (request.method === "DELETE" && status === "200") {
      // The item path's parent is the collection the row belongs to.
      const collection = request.path.replace(/\/[^/]+\/?$/, "");
      deleted.set(collection, (deleted.get(collection) ?? 0) + 1);
    }
  }

  for (const [collection, creates] of created) {
    const removes = deleted.get(collection) ?? 0;
    if (removes < creates) {
      issues.push(
        `${name}.http: ${creates} successful create(s) on ${collection}/ but ${removes} ` +
          "successful delete(s) — running every .http file must leave the database as " +
          "`make db-init` left it",
      );
    }
  }
  return issues;
}

/**
 * One account, one owner. `auth.http` is the only file that creates and deletes
 * the account it logs in as — that lifecycle *is* the auth contract. Every other
 * file authenticates as the seeded actor, declared at the top and created by the
 * seed migration, so `make db-init` is the only prerequisite.
 *
 * The previous rule made each file mint its own actor with `{{$timestamp}}`.
 * That failed block 1 with 409 on any re-run inside the same second (measured),
 * left a stray account behind whenever a run was interrupted, and made three
 * files carry two blocks of setup that had nothing to do with their domain.
 */
function checkActorLifecycle(
  name: string,
  http: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  const authenticated = requests.filter(
    (request) =>
      !isPublicRequest(request) && declaredStatus(sectionTitleFor(sections, request)) !== "401",
  );
  if (authenticated.length === 0) return issues;

  const login = requests.find(
    (request) => request.method === "POST" && request.path.replace(/\/$/, "") === "/auth/login",
  );
  if (login === undefined) return issues; // the structure check already reports this
  const loginBody = blockBody(http, login, requests);

  if (name === "auth") return checkAuthActorLifecycle(http, loginBody, requests, sections);

  // Domain files: log in as the seeded actor, with the credentials written out.
  // A `{{actorUsername}}` indirection was tried and removed: when the client
  // does not resolve it, the body is sent literally and login answers 401 —
  // measured, and indistinguishable from "the file is broken".
  if (!new RegExp(`username=${SEEDED_ACTOR.username}&password=${SEEDED_ACTOR.password}`).test(loginBody)) {
    issues.push(
      `${name}.http: the login block must send the seeded credentials verbatim ` +
        `(username=${SEEDED_ACTOR.username}&password=${SEEDED_ACTOR.password}) — the account ` +
        "comes from the seed migration, and creating one belongs to api/auth.http alone",
    );
  }
  if (!/### 전제:[^\n]*db-init/.test(http)) {
    issues.push(
      `${name}.http: the "### 전제:" line must name \`make db-init\` — the account this file ` +
        "logs in as comes from the seed migration, and a reader must know that",
    );
  }
  if (/#\s*@name\s+createActor\b/.test(http)) {
    issues.push(
      `${name}.http: creates its own actor account — that lifecycle lives in api/auth.http; ` +
        "a per-file actor collides with itself on a re-run inside the same second",
    );
  }
  return issues;
}

/** `auth.http` owns the whole account lifecycle: create → login → delete, last. */
function checkAuthActorLifecycle(
  http: string,
  loginBody: string,
  requests: HttpRequest[],
  sections: HttpSection[],
): string[] {
  const issues: string[] = [];
  const chained = /username=\{\{(\w+)\.response\.body\.username\}\}/.exec(loginBody);
  if (chained === null) {
    issues.push(
      "auth.http: the login block must chain the account it creates " +
        "(username={{createActor.response.body.username}}) — the auth contract is the full " +
        "signup → login → delete lifecycle",
    );
    return issues;
  }
  const actor = chained[1];
  if (!new RegExp(`#\\s*@name\\s+${actor}\\b`).test(http)) {
    issues.push(`auth.http: the login block chains '${actor}', which is not a named block`);
  }
  if (!new RegExp(`^@\\w*[Ii]d\\s*=\\s*\\{\\{${actor}\\.response\\.body\\.id\\}\\}`, "m").test(http)) {
    issues.push(
      `auth.http: missing "@actorId = {{${actor}.response.body.id}}" — the account must be ` +
        "addressable so the file can delete it",
    );
  }
  const last = requests[requests.length - 1];
  const lastStatus = declaredStatus(sectionTitleFor(sections, last));
  if (last.method !== "DELETE" || lastStatus !== "200" || !/^\/user\//.test(last.path)) {
    issues.push(
      "auth.http: the last block must delete the account it created " +
        "(DELETE /user/{{actorId}} — 200) — nothing may follow it, the token dies with it",
    );
  }
  return issues;
}

/**
 * Declaring a state-neutral flow is not proving one. The proof is a runtime
 * target: `make check-api-flow` executes every file and compares row counts
 * before and after. Without the runner and its target, state neutrality is only
 * a comment in a markdown file.
 */
function checkFlowProof(): string[] {
  const issues: string[] = [];
  const runner = join(projectRoot, ".omp", "hooks", "lib", "backend-api-flow.ts");
  if (!existsSync(runner)) {
    issues.push(
      "lib/backend-api-flow.ts is missing — the api/*.http flow has no runtime proof " +
        "(it must execute every file and compare row counts before/after)",
    );
  }
  const makefile = join(projectRoot, "Makefile");
  if (!existsSync(makefile)) return issues;
  const recipe = /^check-api-flow:[^\n]*\n\t([^\n]*)$/m.exec(readFileSync(makefile, "utf-8"));
  if (recipe === null) {
    issues.push(
      "root Makefile has no check-api-flow target — the .http suite must be runnable " +
        "as one command so CI can prove state neutrality",
    );
    return issues;
  }
  if (!recipe[1].includes("backend-api-flow.ts")) {
    issues.push(
      `check-api-flow runs '${recipe[1].trim()}' — it must run lib/backend-api-flow.ts, ` +
        "the runner the standard is verified by",
    );
  }
  return issues;
}

// ============================================================
// Helpers
// ============================================================

function splitBlocks(
  http: string,
  requests: HttpRequest[],
): Array<{ request: HttpRequest; body: string }> {
  return requests.map((request, position) => ({
    request,
    body: http.slice(
      request.index,
      position + 1 < requests.length ? requests[position + 1].index : http.length,
    ),
  }));
}

function isPublicRequest(request: HttpRequest): boolean {
  const path = request.path.replace(/\/$/, "");
  return PUBLIC_REQUESTS.some(
    (open) => open.method === request.method && path === open.path.replace(/\/$/, ""),
  );
}

/**
 * Columns whose value must be unique **on its own**: per-column `unique=True` and
 * single-column `UniqueConstraint(...)`. Composite constraints are excluded on
 * purpose — `UniqueConstraint("provider_id", "name")` is scoped by the parent, so
 * a child created inside a fresh parent may carry a static name, and demanding a
 * guid there reported five violations that were not violations.
 */
function listUniqueColumns(model: string): string[] {
  const columns = new Set<string>();
  for (const match of model.matchAll(/^\s+(\w+):\s*Mapped\[[^\]]*\][^\n]*unique=True/gm)) {
    columns.add(match[1]);
  }
  for (const constraint of model.matchAll(/UniqueConstraint\(([^)]*)\)/g)) {
    const names = [...constraint[1].matchAll(/"(\w+)"/g)].map((name: string[]) => name[1]);
    // The last quoted string is the constraint's own name (name="uq_..."), not a column.
    const scoped = names.filter((candidate: string) => !candidate.startsWith("uq_"));
    if (scoped.length === 1) columns.add(scoped[0]);
  }
  return [...columns];
}

/**
 * The status a section declares, taken from the dash separator: in
 * `### 1. 로그인 계정 준비 — 201 (이미 존재하면 409, 그대로 진행)` the declared status is
 * 201, not the 409 mentioned in the aside. Substring matching would treat every
 * number in the prose as an expectation.
 */
function declaredStatus(title: string): string | null {
  const match = /[—–-]\s*(\d{3})\b/.exec(title);
  return match === null ? null : match[1];
}

/** The numbered section a request belongs to — the nearest header above it. */
function sectionTitleFor(sections: HttpSection[], request: HttpRequest): string {
  let title = "";
  for (const section of sections) {
    if (section.index < request.index) title = section.title;
  }
  return title;
}

function blockBody(http: string, request: HttpRequest, requests: HttpRequest[]): string {
  const block = splitBlocks(http, requests).find((entry) => entry.request.index === request.index);
  return block === undefined ? "" : block.body;
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
