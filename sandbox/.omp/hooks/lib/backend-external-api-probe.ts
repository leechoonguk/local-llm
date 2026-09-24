// @ts-expect-error — Node builtin, not project-compiled
import { spawnSync } from "node:child_process";

/**
 * External API Probe
 *
 * Step 1 of `skill://integration`, mechanised. Every design decision an integration
 * makes comes from a handful of measurements, and a narrated measurement is the one
 * failure the later gates cannot catch: a filter modelled as `QUERY` is accepted by
 * the provider, ignored, and answered 200, so every static reader agrees and the
 * runtime gate sees the declared status match.
 *
 * Measured consequence — an agent asked to run these calls by hand reported four
 * successful calls as throttled, inverted the empty-page case, and concluded the
 * provider accepted a dashed date that actually answers ERROR-601. Seeding from that
 * table would have produced a silently unfiltered operation.
 *
 * So the probe runs the calls and prints what they answered. It draws no conclusion a
 * response does not contain.
 *
 * Usage:
 *   node .omp/hooks/lib/backend-external-api-probe.ts \
 *     --url 'https://host/api/KEY/I2520/json/{start}/{end}' \
 *     [--filter 'RPRSNT_RAWMTRL_NM=김치'] [--since 'CHNG_DT=20240101'] [--root /I2520]
 *
 * `{start}`/`{end}` are required placeholders. `--root` is a JSON pointer prefix to
 * the wrapper (default: the payload's single top-level key).
 */

declare const process: {
  argv: string[];
  exit(code?: number): never;
};

// ============================================================
// Constants
// ============================================================

/** Windows probed as `[start, end, what it answers]`. */
const WINDOWS: ReadonlyArray<readonly [number, number, string]> = [
  [1, 3, "window at the start"],
  [4, 6, "window moved, same size"],
  [1, 10, "window resized"],
  [5, 1, "window inverted"],
];

/** A date far enough ahead that a "changed since" filter must match nothing. */
const FUTURE_DATE = "20991231";

const TIMEOUT_SECONDS = 30;

// ============================================================
// Functions
// ============================================================

export interface ProbeCall {
  label: string;
  url: string;
  status: number | null;
  code: string | null;
  message: string | null;
  total: string | null;
  rows: number | null;
  rowKeys: string[];
}

export function probe(options: {
  url: string;
  filter?: string;
  since?: string;
  root?: string;
}): ProbeCall[] {
  const calls: ProbeCall[] = [];
  for (const [start, end, label] of WINDOWS) {
    calls.push(request(label, window(options.url, start, end), options.root));
  }
  const base = window(options.url, 1, 3);
  if (options.filter !== undefined) {
    calls.push(request("filter as a path segment", `${base}/${encodeExpression(options.filter)}`, options.root));
    calls.push(request("filter as a query string", `${base}?${encodeExpression(options.filter)}`, options.root));
  }
  if (options.since !== undefined) {
    const [key, value] = split(options.since);
    calls.push(request("since filter", `${base}/${key}=${encodeURIComponent(value)}`, options.root));
    calls.push(request("since filter, far future", `${base}/${key}=${FUTURE_DATE}`, options.root));
    calls.push(request("since filter, malformed value", `${base}/${key}=${dashed(value)}`, options.root));
  }
  return calls;
}

function window(template: string, start: number, end: number): string {
  return template.replace("{start}", String(start)).replace("{end}", String(end));
}

function split(expression: string): [string, string] {
  const at = expression.indexOf("=");
  return at < 0 ? [expression, ""] : [expression.slice(0, at), expression.slice(at + 1)];
}

function encodeExpression(expression: string): string {
  return expression
    .split("&")
    .map((pair) => {
      const [key, value] = split(pair);
      return `${key}=${encodeURIComponent(value)}`;
    })
    .join("&");
}

/** `20240101` -> `2024-01-01`: the shape a provider's own docs often reject. (history-ok: format example) */
function dashed(value: string): string {
  return /^\d{8}$/.test(value)
    ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6)}`
    : `${value}-`;
}

function request(label: string, url: string, root: string | undefined): ProbeCall {
  const result = spawnSync(
    "curl",
    ["-s", "-m", String(TIMEOUT_SECONDS), "-w", "\\n%{http_code}", url],
    { encoding: "utf-8", maxBuffer: 32 * 1024 * 1024 },
  );
  const body = String(result.stdout ?? "");
  const boundary = body.lastIndexOf("\n");
  const status = Number.parseInt(body.slice(boundary + 1).trim(), 10);
  let payload: unknown;
  try {
    payload = JSON.parse(body.slice(0, boundary));
  } catch {
    payload = null;
  }
  const wrapper = readWrapper(payload, root);
  return {
    label,
    url,
    status: Number.isNaN(status) ? null : status,
    code: wrapper.code,
    message: wrapper.message,
    total: wrapper.total,
    rows: wrapper.rows === null ? null : wrapper.rows.length,
    rowKeys: wrapper.rowKeys,
  };
}

/** The four things a wrapper answers, read once at the boundary. */
interface ProbeWrapper {
  code: string | null;
  message: string | null;
  total: string | null;
  rows: unknown[] | null;
  rowKeys: string[];
}

/**
 * Read the response wrapper: `--root` names it, otherwise it is the payload's single
 * top-level key (`{"I2520": {…}}`).
 */
function readWrapper(payload: unknown, root: string | undefined): ProbeWrapper {
  let node: unknown = payload;
  const path = root !== undefined ? root.split("/").filter((piece) => piece.length > 0) : soleKey(payload);
  for (const part of path) node = field(node, part);
  const rowsValue = field(node, "row");
  const rows = Array.isArray(rowsValue) ? rowsValue : null;
  const code = field(field(node, "RESULT"), "CODE");
  const message = field(field(node, "RESULT"), "MSG");
  const total = field(node, "total_count");
  const firstRow = rows !== null && rows.length > 0 ? rows[0] : null;
  return {
    code: typeof code === "string" ? code : null,
    message: typeof message === "string" ? message : null,
    total: typeof total === "string" || typeof total === "number" ? String(total) : null,
    rows,
    rowKeys:
      typeof firstRow === "object" && firstRow !== null && !Array.isArray(firstRow)
        ? Object.keys(firstRow)
        : [],
  };
}

/** One property of a decoded JSON node, or undefined when the node has no properties. */
function field(node: unknown, key: string): unknown {
  if (typeof node !== "object" || node === null || Array.isArray(node)) return undefined;
  return (node as { [property: string]: unknown })[key];
}

/** `{"I2520": {…}}` -> `["I2520"]`; anything else has no single wrapper to unwrap. */
function soleKey(payload: unknown): string[] {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) return [];
  const keys = Object.keys(payload);
  return keys.length === 1 ? keys : [];
}

function report(calls: ProbeCall[]): void {
  console.log("==> external-api-probe");
  console.log("");
  console.log("| case | HTTP | code | total_count | rows |");
  console.log("|---|---|---|---|---|");
  for (const call of calls) {
    console.log(
      `| ${call.label} | ${call.status ?? "-"} | ${call.code ?? "-"} | ${call.total ?? "-"} | ${call.rows ?? "absent"} |`,
    );
  }
  console.log("");
  for (const call of calls) {
    if (call.message !== null) console.log(`  ${call.label}: ${call.code} ${call.message}`);
  }
  const shaped = calls.find((call) => call.rowKeys.length > 0);
  if (shaped !== undefined) {
    console.log("");
    console.log(`  row columns (${shaped.rowKeys.length}): ${shaped.rowKeys.join(", ")}`);
  }
  const path = calls.find((call) => call.label === "filter as a path segment");
  const query = calls.find((call) => call.label === "filter as a query string");
  if (path !== undefined && query !== undefined) {
    console.log("");
    console.log(
      `  filter totals — path segment: ${path.total ?? "-"}, query string: ${query.total ?? "-"}`,
    );
    console.log(
      "  (equal totals mean the provider ignored one of them; that transport is not a filter)",
    );
  }
}

// Direct execution (make probe-external-api): run the calls and print the table.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("backend-external-api-probe.ts")) {
  const argv = process.argv.slice(2);
  const flag = (name: string): string | undefined => {
    const at = argv.indexOf(`--${name}`);
    return at < 0 ? undefined : argv[at + 1];
  };
  const url = flag("url");
  if (url === undefined || !url.includes("{start}") || !url.includes("{end}")) {
    console.error(
      "usage: --url 'https://host/api/KEY/SERVICE/json/{start}/{end}' [--filter 'K=V'] [--since 'K=YYYYMMDD'] [--root /WRAPPER]",
    );
    process.exit(2);
  }
  report(probe({ url, filter: flag("filter"), since: flag("since"), root: flag("root") }));
}
