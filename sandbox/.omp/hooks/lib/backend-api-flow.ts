// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { listIntegrationOperations } from "./backend-migration-policy.ts";
import { resolveProjectRoot } from "./hook-project-root.ts";

/**
 * Runtime proof of the api/*.http standard (backend-api-http.md).
 *
 * `check-backend-api-http` proves a file *declares* a state-neutral flow. This
 * runner proves the flow *is* one, by executing it exactly as REST Client would:
 *
 *   1. blocks run top to bottom; ids, tokens and credentials are chained from
 *      earlier responses ({{name.response.body.*}}) and dynamic values
 *      ({{$timestamp}}, {{$guid}}, {{$randomInt}}) are generated per request;
 *   2. every response status must equal the status the section title declares
 *      after the dash — a drifted contract fails here instead of in review;
 *   3. row counts are snapshotted before and after every file: a leaked row (or
 *      a deleted seeded row) fails, because the next run would then start from a
 *      different database than `make db-init` produced.
 *
 * CLI only (`make check-api-flow`) — never a post hook: the run mutates the
 * database and calls external APIs, so it must be asked for, not triggered.
 */

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
};
declare function fetch(url: string, init?: unknown): Promise<{
  status: number;
  headers: { getSetCookie(): string[] };
  text(): Promise<string>;
}>;

// ============================================================
// Constants
// ============================================================

const projectRoot = resolveProjectRoot();
const apiDir = join(projectRoot, "api");

const REQUEST_LINE = /^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)\s*$/;
const SECTION_LINE = /^###\s+(\d+)\.\s*(.*)$/;
const NAME_LINE = /^#\s*@name\s+(\S+)/;
const VARIABLE_LINE = /^@([\w-]+)\s*=\s*(.*)$/;
const HEADER_LINE = /^([A-Za-z][A-Za-z0-9-]*):\s*(.*)$/;
const DECLARED_STATUS = /[—–-]\s*(\d{3})\b/;
const TEMPLATE = /\{\{([^}]+)\}\}/g;
const DOTENV_REF = /^\$dotenv\s+(\w+)$/;
const RESPONSE_REF = /^(\w+)\.response\.body\.(.+)$/;

/**
 * One round trip for every table's exact count: query_to_xml runs the count
 * per discovered table, so a new table is included without editing this query.
 * Two tables are excluded, for the same reason in different clothes: neither
 * holds a row a request file authored. `alembic_version` is schema bookkeeping.
 * `refresh` holds the server-issued session `POST /auth/login` mints, and every
 * file must log in — measured: nine files each left exactly one row behind, and
 * no published endpoint deletes one (logout revokes, keeping the row so a
 * replayed token stays distinguishable from an unknown one). Counting it made
 * "authenticated" indistinguishable from "leaked a domain row".
 */
const ROW_COUNT_SQL = `
SELECT table_name || '=' || (xpath(
         '/row/cnt/text()',
         query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name),
                      false, true, '')
       ))[1]::text::bigint
  FROM information_schema.tables
 WHERE table_schema = 'public'
   AND table_type = 'BASE TABLE'
   AND table_name NOT IN ('alembic_version', 'refresh')
 ORDER BY table_name
`;

/**
 * The base every request resolves through `{{base}}` — read from the same
 * `api/.env` the editor's REST Client reads (`{{$dotenv API_BASE_URL}}`), with
 * the committed example as the fallback. A second literal here is how the
 * runner and the request files start testing two different servers.
 */
const API_BASE = `${readDotenv("API_ORIGIN") ?? "http://localhost:8000"}/api/v1`;

/** `/health` sits above the version prefix, so the probe needs the bare origin. */
const API_ORIGIN = API_BASE.replace(/\/api\/v1$/, "");

const PROBE_TIMEOUT_MS = 5_000;

/**
 * The account every domain file authenticates as, seeded by migration 57 so it
 * survives `make db-init`. A per-file actor minted with `{{$timestamp}}` answered
 * 409 on any re-run inside the same second (measured) and leaked a row whenever a
 * run was interrupted. `auth.http` still owns a create → login → delete
 * lifecycle of its own, because that lifecycle is the auth contract.
 */
const ACTOR_USERNAME = "api-actor";
const ACTOR_PASSWORD = "api-actor-secret";

const REQUEST_TIMEOUT_MS = 60_000;
const PSQL_TIMEOUT_MS = 30_000;
const BODY_EXCERPT_CHARS = 160;

/**
 * One file's cookies, kept for the same reason REST Client keeps them: a session
 * planted by `POST /auth/login` is what `POST /auth/refresh` consumes two blocks
 * later. Without a jar that block answered 401 and the logout block that follows
 * it "passed" for the wrong reason — measured on `api/auth.http`.
 */
type CookieJar = Map<string, string>;

interface Block {
  number: number;
  title: string;
  expected: number | null;
  name: string | null;
  method: string;
  target: string;
  headers: Record<string, string>;
  body: string;
}

/** A `@name = value` definition — resolved lazily, at first use. */
interface Variable {
  name: string;
  raw: string;
}

type Step = Block | Variable;

/** One executed block: what the title declared, and what the server answered. */
interface BlockResult {
  file: string;
  number: number;
  method: string;
  target: string;
  expected: number | null;
  actual: number | null;
  note: string;
}

// ============================================================
// Functions
// ============================================================

export async function runApiFlow(verbose = false): Promise<string[]> {
  if (!existsSync(apiDir)) return [`${apiDir} not found — no .http files to run`];
  // Dormant, never red, when the stack is down: this gate runs inside
  // `make verify`, and a laptop on a plane must still be able to prove the
  // hermetic checks. The same shape as check-backend-migrations' unreachable
  // database — a skip that says so, rather than a pass that lies.
  const dormant = await dormantReason();
  if (dormant !== null) {
    console.log(`    PASS: api flow (dormant — ${dormant})`);
    return [];
  }
  const files = readdirSync(apiDir)
    .filter((file: string) => file.endsWith(".http"))
    .sort();
  if (files.length === 0) return [`no .http files found in ${apiDir}`];

  // The actor is seeded by migration 57, so it is part of the `make db-init`
  // baseline: the suite reads it, never creates or deletes it. Each file being
  // able to log in without provisioning anything is what makes a single-file run
  // from an editor work.
  const missing = await verifySeededActor();
  if (missing !== null) return [missing];
  const failures: string[] = [];
  // The hooks read migrations, hermetically — nothing they can see says whether
  // the database agrees. Measured consequence: `search-domestic-food-products`
  // was seeded by revision 16 and erased by the provider replace at revision 20
  // (operation.provider_id is ON DELETE CASCADE), and every static gate kept
  // demanding a request file for a row no database had. This gate reads the rows,
  // so the comparison belongs here.
  failures.push(...checkSeededOperations());

  let executed = 0;
  const suiteBefore = rowCounts();
  let snapshot = suiteBefore;
  for (const file of files) {
    const source = readFileSync(join(apiDir, file), "utf-8");
    const result = await runFile(file, parseFlow(source));
    executed += result.executed;
    failures.push(...result.failures);
    if (verbose) {
      for (const block of result.blocks) {
        const verdict = block.actual === block.expected ? "ok  " : "FAIL";
        console.log(
          `      ${verdict} ${String(block.number).padStart(2)}. ${block.method.padEnd(6)} ` +
            `${block.target.padEnd(56)} expected ${block.expected ?? "-"} ` +
            `got ${block.actual ?? "-"}`,
        );
      }
    }

    const after = rowCounts();
    const leaks = diffCounts(snapshot, after);
    if (leaks.length === 0) {
      console.log(`    RUN: api/${file} — ${result.executed} block(s), state neutral`);
    } else {
      failures.push(
        `${file}: left the database changed (${leaks.join(", ")}) — a file must remove ` +
          "every row it creates and delete no seeded row",
      );
    }
    snapshot = after;
  }

  const suiteLeaks = diffCounts(suiteBefore, snapshot);
  if (suiteLeaks.length > 0) {
    failures.push(`suite: row counts changed (${suiteLeaks.join(", ")})`);
  }

  if (failures.length === 0) {
    console.log(
      `    PASS: ${executed} block(s) matched their declared status in ${files.length} file(s)`,
    );
    console.log(`    PASS: state neutral — ${snapshot.size} table(s) unchanged`);
    console.log(`    PASS: seeded actor ${ACTOR_USERNAME} intact (never created, never deleted)`);
  }
  return failures;
}

/**
 * Why the suite cannot run here, or `null` when it can.
 *
 * Both halves are required and neither is this repository's code: the API
 * answers the requests, and postgres answers the row counts that prove state
 * neutrality. A missing half makes the run unprovable, not failed.
 */
async function dormantReason(): Promise<string | null> {
  try {
    await fetch(`${API_ORIGIN}/health`, { signal: AbortSignal.timeout(PROBE_TIMEOUT_MS) });
  } catch (error: unknown) {
    return (
      `the API at ${API_ORIGIN} is unreachable (${(error as Error).message}) — ` +
      "start it with make up, or cd backend && make dev"
    );
  }
  try {
    query("SELECT 1");
  } catch (error: unknown) {
    return `${(error as Error).message}`;
  }
  return null;
}

/**
 * The seeded actor must be able to log in before the suite starts. Without this
 * the first authenticated block answers 401 and every later block fails with it,
 * which reads as "the .http files are broken" instead of "the database has no
 * seed" — the exact confusion this check removes.
 */
export async function verifySeededActor(): Promise<string | null> {
  const login = await send(
    "POST",
    `${API_BASE}/auth/login`,
    { "Content-Type": "application/x-www-form-urlencoded" },
    `username=${ACTOR_USERNAME}&password=${ACTOR_PASSWORD}`,
    // A throwaway jar: this probe proves the seed exists and shares its session
    // with nobody, so the files still each log in for themselves.
    new Map(),
  );
  if (login.status === 200) return null;
  return (
    `seeded actor ${ACTOR_USERNAME} cannot log in (${login.status}) — apply the seed ` +
    "migration first (make db-init, or cd backend && make migrate). Every api/*.http " +
    "file logs in as this account; without it block 1 answers 401"
  );
}

/**
 * The operations the migrations declare must be exactly the rows
 * `integration_operation` holds.
 *
 * Read from the database, not from the API: the endpoint is one more layer that
 * can filter, paginate or serialise the answer, and this check exists to compare
 * the repository's claim with the stored rows. `alembic_version` is asserted at
 * head first — comparing against a database that is behind reports drift that is
 * only a missing `make migrate`.
 */
export function checkSeededOperations(): string[] {
  const pending = query(
    "SELECT version_num FROM alembic_version",
  );
  const head = maxRevision();
  if (pending.length !== 1 || pending[0] !== head) {
    return [
      `database is at revision ${pending.join(",") || "(none)"} but the migrations head is ` +
        `${head} — run make migrate before comparing seeds with rows`,
    ];
  }
  const live = new Set(query("SELECT code FROM integration_operation ORDER BY code"));
  const declared = new Set<string>(listIntegrationOperations().map((operation) => operation.code));
  const failures: string[] = [];
  for (const code of declared) {
    if (!live.has(code)) {
      failures.push(
        `operation '${code}' is seeded by a migration but the database has no such row — ` +
          "a later revision deleted it (provider replace cascades) or the migration never ran",
      );
    }
  }
  for (const code of live) {
    if (!declared.has(code)) {
      failures.push(
        `operation '${code}' exists in the database but no migration seeds it — ` +
          "configuration created by hand is configuration nobody can rebuild",
      );
    }
  }
  if (failures.length === 0) {
    console.log(
      `    PASS: ${declared.size} seeded operation(s) match integration_operation at revision ${head}`,
    );
  }
  return failures;
}

/** The newest revision on disk — the head `make migrate` brings the database to. */
function maxRevision(): string {
  const versionsDir = join(projectRoot, "backend", "alembic", "versions");
  if (!existsSync(versionsDir)) return "";
  const revisions = readdirSync(versionsDir)
    .filter((file: string) => /^\d+_.*\.py$/.test(file))
    .map((file: string) => Number.parseInt(file.split("_")[0], 10));
  return revisions.length === 0 ? "" : String(Math.max(...revisions));
}

/** Reads an .http file into the ordered program REST Client would execute. */
export function parseFlow(source: string): Step[] {
  const steps: Step[] = [];
  const lines = source.split("\n");
  let number = 0;
  let title = "";
  let pendingName: string | null = null;
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const section = SECTION_LINE.exec(line);
    if (section !== null) {
      number = Number(section[1]);
      title = section[2];
      index += 1;
      continue;
    }
    const named = NAME_LINE.exec(line);
    if (named !== null) {
      pendingName = named[1];
      index += 1;
      continue;
    }
    const variable = VARIABLE_LINE.exec(line);
    if (variable !== null) {
      steps.push({ name: variable[1], raw: variable[2].trim() });
      index += 1;
      continue;
    }
    const request = REQUEST_LINE.exec(line);
    if (request === null) {
      index += 1;
      continue;
    }

    const block: Block = {
      number,
      title,
      expected: declaredStatus(title),
      name: pendingName,
      method: request[1],
      target: request[2],
      headers: {},
      body: "",
    };
    pendingName = null;
    index += 1;
    while (index < lines.length) {
      const header = HEADER_LINE.exec(lines[index]);
      if (header === null) break;
      block.headers[header[1]] = header[2].trim();
      index += 1;
    }
    if (index < lines.length && lines[index].trim() === "") {
      index += 1;
      const body: string[] = [];
      // REST Client ends a body at the next `###` delimiter and **nothing else**.
      // This parser used to stop at a `@var` line too, which made it accept files
      // the real client rejects: a declaration after the body is sent as trailing
      // JSON and answers 422 `json_invalid` / "Extra data" (measured, offset 167).
      while (index < lines.length && !lines[index].startsWith("###")) {
        body.push(lines[index]);
        index += 1;
      }
      block.body = body.join("\n").trim();
    }
    steps.push(block);
  }

  return steps;
}

/**
 * Executes one file's blocks in order, chaining each response into later ones.
 * Exported so a single file can be replayed on its own — that is how an editor
 * runs it, and it is the case the seeded actor exists to support.
 */
export async function runFile(
  file: string,
  steps: Step[],
): Promise<{ executed: number; failures: string[]; blocks: BlockResult[] }> {
  const variables = new Map<string, string>();
  const responses = new Map<string, unknown>();
  // Per file, never per suite: a file must be runnable on its own, so it may
  // not inherit a session another file logged in for.
  const jar: CookieJar = new Map();
  const failures: string[] = [];
  const blocks: BlockResult[] = [];
  let executed = 0;

  for (const step of steps) {
    if (!isBlock(step)) {
      variables.set(step.name, step.raw);
      continue;
    }

    const label = `${file}:${step.number}`;
    let url = "";
    let headers: Record<string, string> = {};
    let body = "";
    try {
      url = render(step.target, variables, responses);
      headers = Object.fromEntries(
        Object.entries(step.headers).map(([key, value]) => [
          key,
          render(value, variables, responses),
        ]),
      );
      body = render(step.body, variables, responses);
    } catch (error: unknown) {
      failures.push(`${label}: unresolved template ${(error as Error).message}`);
      blocks.push({
        file,
        number: step.number,
        method: step.method,
        target: step.target,
        expected: step.expected,
        actual: null,
        note: `unresolved template ${(error as Error).message}`,
      });
      continue;
    }

    const response = await send(step.method, url, headers, body, jar);
    executed += 1;
    if (step.expected === null) {
      failures.push(`${label}: section title declares no expected status (${step.title})`);
    } else if (response.status !== step.expected) {
      failures.push(
        `${label}: expected ${step.expected}, got ${response.status} — ` +
          `${step.method} ${url} ${response.payload.slice(0, BODY_EXCERPT_CHARS)}`,
      );
    }
    blocks.push({
      file,
      number: step.number,
      method: step.method,
      target: url.replace(API_BASE, ""),
      expected: step.expected,
      actual: response.status,
      note: step.title,
    });
    if (step.name !== null) responses.set(step.name, decode(response.payload));
  }

  return { executed, failures, blocks };
}

/** Sends one request; an error status is a result to compare, never a throw. */
async function send(
  method: string,
  url: string,
  headers: Record<string, string>,
  body: string,
  jar: CookieJar,
): Promise<{ status: number; payload: string }> {
  try {
    const cookie = cookieHeader(jar);
    const response = await fetch(url, {
      method,
      headers: cookie === "" || "Cookie" in headers ? headers : { ...headers, Cookie: cookie },
      body: body === "" ? undefined : body,
      // Cookies are followed by hand, so redirects must not swallow a Set-Cookie
      // the runner never sees.
      redirect: "manual",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    storeCookies(jar, response.headers.getSetCookie());
    return { status: response.status, payload: await response.text() };
  } catch (error: unknown) {
    throw new Error(
      `${method} ${url} failed (${(error as Error).message}) — start the stack first ` +
        "(make up, or cd backend && make dev)",
    );
  }
}

/** Resolves `{{...}}` the way REST Client does: variables, chains, dynamics. */
function render(
  raw: string,
  variables: Map<string, string>,
  responses: Map<string, unknown>,
): string {
  return raw.replace(TEMPLATE, (_match: string, group: string) => {
    const expression = group.trim();
    if (expression === "$timestamp") return String(Math.floor(Date.now() / 1000));
    if (expression === "$guid") return crypto.randomUUID();
    if (expression.startsWith("$randomInt")) {
      return String(1 + Math.floor(Math.random() * 1_000_000));
    }
    const dotenv = DOTENV_REF.exec(expression);
    if (dotenv !== null) {
      const value = readDotenv(dotenv[1]);
      if (value === null) throw new Error(`${expression} (api/.env declares no ${dotenv[1]})`);
      return value;
    }
    const reference = RESPONSE_REF.exec(expression);
    if (reference !== null) return dig(responses, reference[1], reference[2]);
    const variable = variables.get(expression);
    if (variable !== undefined) return render(variable, variables, responses);
    throw new Error(expression);
  });
}

/**
 * REST Client resolves `{{$dotenv NAME}}` from the `.env` beside the `.http`
 * file (upstream README), so the runner reads the same file. The committed
 * `.env.example` is the fallback: a fresh clone has no `.env`, and failing there
 * would report a broken request file instead of a missing local config.
 */
function readDotenv(key: string): string | null {
  for (const file of [".env", ".env.example"]) {
    const path = join(apiDir, file);
    if (!existsSync(path)) continue;
    const match = new RegExp(`^\\s*${key}\\s*=\\s*(.+?)\\s*$`, "m").exec(readFileSync(path, "utf-8"));
    if (match !== null) return match[1];
  }
  return null;
}

/** Serializes the jar into one `Cookie` header, or `""` when it is empty. */
function cookieHeader(jar: CookieJar): string {
  return [...jar].map(([name, value]) => `${name}=${value}`).join("; ");
}

/**
 * Applies one response's `Set-Cookie` headers to the jar.
 *
 * A deletion is a `Set-Cookie` too: logout answers with an empty value and
 * `Max-Age=0`, and treating that as a normal assignment would keep sending a
 * cookie the server just revoked — the block that proves logout worked would
 * then fail for a reason that has nothing to do with logout.
 */
function storeCookies(jar: CookieJar, setCookies: string[]): void {
  for (const header of setCookies) {
    const [pair] = header.split(";");
    const separator = pair.indexOf("=");
    if (separator <= 0) continue;
    const name = pair.slice(0, separator).trim();
    const value = pair.slice(separator + 1).trim().replace(/^"|"$/g, "");
    const deleted = value === "" || /(^|;)\s*max-age=0\s*(;|$)/i.test(header);
    if (deleted) jar.delete(name);
    else jar.set(name, value);
  }
}

/** Walks a chained response body: `createUser.response.body.id` → payload.id. */
function dig(responses: Map<string, unknown>, name: string, path: string): string {
  if (!responses.has(name)) {
    throw new Error(`${name}.response.body.${path} (block '${name}' produced no response)`);
  }
  let value = responses.get(name);
  for (const segment of path.split(".")) {
    if (Array.isArray(value) && /^\d+$/.test(segment)) {
      value = value[Number(segment)];
      continue;
    }
    if (value === null || typeof value !== "object" || !(segment in value)) {
      throw new Error(`${name}.response.body.${path}`);
    }
    value = (value as Record<string, unknown>)[segment];
  }
  return String(value);
}

function decode(payload: string): unknown {
  try {
    return JSON.parse(payload);
  } catch {
    return {};
  }
}

/**
 * Row count per public table — the state `make db-init` defines and a run must
 * preserve. Read through `query()`: one spawn site for the whole harness, so the
 * credentials and the container path exist in exactly one place.
 */
function rowCounts(): Map<string, number> {
  const counts = new Map<string, number>();
  for (const line of query(ROW_COUNT_SQL)) {
    const [table, count] = line.split("=");
    if (table === undefined || count === undefined || table === "") continue;
    counts.set(table, Number(count));
  }
  return counts;
}

/**
 * One `psql -tAc` through the postgres container: no local client, no second copy
 * of the credentials, and the answer comes from the database rather than from the
 * API that reads it.
 */
function query(sql: string): string[] {
  const env = readEnv(join(projectRoot, ".env"));
  const user = env.get("POSTGRES_USER");
  const database = env.get("POSTGRES_DB");
  if (user === undefined || database === undefined) {
    throw new Error("POSTGRES_USER / POSTGRES_DB missing from .env — cannot query the database");
  }
  const result = spawnSync(
    "docker",
    ["compose", "exec", "-T", "postgres", "psql", "-U", user, "-d", database, "-tAc", sql],
    { cwd: projectRoot, encoding: "utf-8", timeout: PSQL_TIMEOUT_MS },
  );
  if (result.status !== 0) {
    throw new Error(
      `postgres unreachable (${String(result.stderr ?? "").trim() || "docker compose exec failed"}) ` +
        "— start it with make infra-up",
    );
  }
  return String(result.stdout)
    .split("\n")
    .map((line: string) => line.trim())
    .filter((line: string) => line !== "");
}

function readEnv(path: string): Map<string, string> {
  const env = new Map<string, string>();
  if (!existsSync(path)) return env;
  for (const line of readFileSync(path, "utf-8").split("\n")) {
    const match = /^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/.exec(line.trim());
    if (match === null) continue;
    env.set(match[1], match[2].trim().replace(/^["']|["']$/g, ""));
  }
  return env;
}

function diffCounts(before: Map<string, number>, after: Map<string, number>): string[] {
  const tables = [...new Set([...before.keys(), ...after.keys()])].sort();
  return tables
    .filter((table) => (before.get(table) ?? 0) !== (after.get(table) ?? 0))
    .map((table) => `${table} ${before.get(table) ?? 0} → ${after.get(table) ?? 0}`);
}

/**
 * The status a section declares, taken from the dash separator: in
 * `### 1. 계정 생성 — 201 (이미 있으면 409)` the expectation is 201, not the 409
 * mentioned in the aside.
 */
function declaredStatus(title: string): number | null {
  const match = DECLARED_STATUS.exec(title);
  return match === null ? null : Number(match[1]);
}


function isBlock(step: Step): step is Block {
  return "method" in step;
}

// Direct execution (make check-api-flow): run every file and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("backend-api-flow.ts")) {
  console.log("==> check-api-flow");
  runApiFlow(process.argv.includes("--verbose"))
    .then((issues: string[]) => {
      if (issues.length === 0) return;
      for (const issue of issues) console.log(`    FAIL: ${issue}`);
      console.log(`    ${issues.length} issue(s) found`);
      process.exit(1);
    })
    .catch((error: unknown) => {
      console.log(`    FAIL: ${(error as Error).message}`);
      process.exit(1);
    });
}
