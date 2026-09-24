import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { ledgerTablesOf } from "../lib/backend-ledger-feeds.ts";
import {
  SRC_DIRECTORIES,
  discoverDomains,
  frontendSrc,
  label,
  pascalCase,
  projectRoot,
  readIfPresent,
} from "../lib/frontend-source.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-Domain Post Hook
 *
 * Validates the frontend 6-layer domain pattern from
 * .omp/rules/frontend-domain.md. A domain is a `<name>.service.ts`, and every
 * domain must carry the whole set:
 *
 *   types/<domain>.ts        the wire types
 *   lib/api/endpoints.ts     <DOMAIN>_ENDPOINTS
 *   lib/api/queryKeys.ts     <domain>Keys
 *   services/<domain>.service.ts   list/detail/create/update/remove
 *   hooks/use<Domain>.ts     list/detail/create/update/delete hooks
 *   sections/<domain>/       <Domain>List.tsx + <Domain>FormDialog.tsx
 *                            (no dialog when the list creates rows in the grid)
 *   pages/<Domain>Page.tsx   the route component
 *
 * A half-built domain is the failure this prevents: a service with no hook is
 * called from a screen directly, and a screen with no page is unreachable.
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/** Every CRUD verb a resource service must expose, in the order it is read. */
const SERVICE_METHODS = ["list", "detail", "create", "update", "remove"];

export default function checkFrontendDomain(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-domain", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendDomainSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-domain");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-domain",
      issues,
      "run make check-frontend-domain for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-domain") };
  }));
}

export function checkFrontendDomainSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  const domains = discoverDomains();
  if (domains.length === 0) {
    return [`${label(SRC_DIRECTORIES.services)}: no <domain>.service.ts — the app has no domain`];
  }

  const endpoints = readIfPresent(join(SRC_DIRECTORIES.lib, "endpoints.ts")) ?? "";
  const queryKeys = readIfPresent(join(SRC_DIRECTORIES.lib, "queryKeys.ts")) ?? "";

  for (const domain of domains) {
    const name = pascalCase(domain);
    if (isLedgerDomain(domain)) {
      issues.push(...checkLedgerDomain(domain, name, queryKeys));
    } else {
      issues.push(...checkLayerFiles(domain, name));
      issues.push(...checkServiceMethods(domain));
      issues.push(...checkQueryHooks(domain, name));
    }

    if (!new RegExp(`${domain.toUpperCase()}_ENDPOINTS\\s*=`).test(endpoints)) {
      issues.push(
        `frontend/src/lib/api/endpoints.ts: no ${domain.toUpperCase()}_ENDPOINTS — ` +
          `the ${domain} service would carry its URLs inline`,
      );
    }
    if (!isLedgerDomain(domain) && !new RegExp(`${domain}Keys\\s*=\\s*createQueryKeys`).test(queryKeys)) {
      issues.push(
        `frontend/src/lib/api/queryKeys.ts: no ${domain}Keys — ` +
          `the ${domain} hooks cannot share an invalidation key`,
      );
    }
  }

  issues.push(...checkOrphanSections(domains));
  return issues;
}

/**
 * A domain is a ledger when a provider job replaces its tables feed by feed -
 * the `FEEDS` of `backend/app/batch/sync_<provider>_ledgers.py`, the same fact
 * `check-backend-domain` reads to make the router read-only.
 */
function isLedgerDomain(domain: string): boolean {
  return ledgerTablesOf(join(projectRoot, "backend", "app"), domain).length > 0;
}

/**
 * The layers of a **ledger domain**: one read surface per derived table it
 * shows, no write surface, and no screen on a ledger itself.
 *
 * The rows are a function of the ledgers, rebuilt every night, so the CRUD
 * template's form dialog, create/update/remove service methods and mutation
 * hooks are not merely optional here - they are refused, because each would
 * edit a copy the next rebuild overwrites. Per table rather than per domain:
 * `food` derives several tables, and each screen
 * (`<Domain><Table>DerivedList.tsx`) owes its own hook, page and query key.
 */
function checkLedgerDomain(domain: string, name: string, queryKeys: string): string[] {
  const issues: string[] = [];
  const sectionDir = join(SRC_DIRECTORIES.sections, domain);
  const screens = existsSync(sectionDir)
    ? readdirSync(sectionDir).filter((f: string) => f.endsWith("DerivedList.tsx"))
    : [];
  if (screens.length === 0) {
    issues.push(`${label(sectionDir)}: a ledger domain with no <${name}><Table>DerivedList.tsx - nothing shows the derived rows`);
  }
  const typesPath = join(SRC_DIRECTORIES.types, `${domain}.ts`);
  if (!existsSync(typesPath)) issues.push(`${label(typesPath)}: missing — the ${domain} domain is incomplete`);
  const hooksPath = join(SRC_DIRECTORIES.queryHooks, `use${name}.ts`);
  const hooks = readIfPresent(hooksPath) ?? "";
  if (hooks === "") issues.push(`${label(hooksPath)}: missing — the ${domain} domain is incomplete`);
  const servicePath = join(SRC_DIRECTORIES.services, `${domain}.service.ts`);
  const service = readIfPresent(servicePath) ?? "";
  const types = readIfPresent(typesPath) ?? "";

  for (const screen of screens) {
    const table = screen.replace(/DerivedList\.tsx$/, "").replace(new RegExp(`^${name}`), "");
    const page = join(SRC_DIRECTORIES.pages, `${name}${table}Page.tsx`);
    if (!existsSync(page)) issues.push(`${label(page)}: missing — the ${domain} derived ${table} has no route component`);
    if (!new RegExp(`export function use${name}${table}List\\b`).test(hooks)) {
      issues.push(`${label(hooksPath)}: no exported use${name}${table}List — the ${table} derived table has no query`);
    }
    const key = `${domain}${table}Keys`;
    if (!new RegExp(`${key}\\s*=\\s*createQueryKeys`).test(queryKeys)) {
      issues.push(`frontend/src/lib/api/queryKeys.ts: no ${key} — the ${table} derived table's hook cannot name its cache`);
    }
  }
  if (!/\blist\w*\s*:/.test(service)) {
    issues.push(`${label(servicePath)}: no list*() — a ledger domain's service reads pages and records, nothing else`);
  }
  for (const method of ["create", "update", "remove"]) {
    if (new RegExp(`\\b${method}\\w*\\s*:`).test(service)) {
      issues.push(`${label(servicePath)}: has ${method}() on a ledger domain — the rows are a nightly sync's, and a write here is overwritten by morning`);
    }
  }
  for (const hook of [`useCreate${name}`, `useUpdate${name}`, `useDelete${name}`]) {
    if (new RegExp(`export function ${hook}\\w*\\b`).test(hooks)) {
      issues.push(`${label(hooksPath)}: exports ${hook}* on a ledger domain — no mutation may exist for rows a sync owns`);
    }
  }
  if (/CreateRequest|UpdateRequest/.test(types)) {
    issues.push(`${label(typesPath)}: declares a CreateRequest/UpdateRequest on a ledger domain — there is no request that writes these rows`);
  }
  const dialog = existsSync(sectionDir)
    ? readdirSync(sectionDir).find((f: string) => f.endsWith("FormDialog.tsx"))
    : undefined;
  if (dialog !== undefined) {
    issues.push(`${label(join(sectionDir, dialog))}: a form dialog on a ledger domain — nothing here may write a row`);
  }
  return issues;
}

/**
 * Every layer that is one file per domain.
 *
 * The form dialog is required *unless* the list creates its rows in the grid. A
 * screen whose whole record is a row — three scalars on `/user` — makes the row
 * the form: `+` opens a draft row, saving it is the create, and a dialog beside
 * that would be a second surface asking for the same fields, drifting in order
 * and in lengths the moment either side changed. The exemption is read from the
 * list itself (a draft row that saves through `processRowUpdate`), so deleting
 * the dialog without moving creation into the grid still fails here.
 */
function checkLayerFiles(domain: string, name: string): string[] {
  const issues: string[] = [];
  const listPath = join(SRC_DIRECTORIES.sections, domain, `${name}List.tsx`);
  const list = readIfPresent(listPath) ?? "";
  const createsInGrid = /\bisNew\b/.test(list) && /processRowUpdate/.test(list);
  issues.push(...checkCreateSurface(domain, name, list, createsInGrid));
  const required = [
    join(SRC_DIRECTORIES.types, `${domain}.ts`),
    join(SRC_DIRECTORIES.queryHooks, `use${name}.ts`),
    listPath,
    ...(createsInGrid ? [] : [join(SRC_DIRECTORIES.sections, domain, `${name}FormDialog.tsx`)]),
    join(SRC_DIRECTORIES.pages, `${name}Page.tsx`),
  ];
  for (const path of required) {
    if (!existsSync(path)) {
      issues.push(`${label(path)}: missing — the ${domain} domain is incomplete`);
    }
  }
  return issues;
}

/**
 * Where a record is created is decided by the record, not by taste.
 *
 * **Is every field of the create an editable column?** Then the row *is* the
 * form and the dialog is a second surface asking for the same fields: `/user`
 * writes `username`, `email`, `password`, and all three are editable columns, so
 * `+` opens a draft row. When one field cannot be a cell the dialog stays —
 * `/batch` writes a multiline `description` that is no column, `/integration`
 * writes nested `secrets`.
 *
 * Documented, the criterion was still a matter of opinion: a domain of three
 * scalars could keep a dialog and nothing would say so. It is read from the two
 * files that already state it — the create request type and the list's editable
 * columns — so the answer moves the moment either does.
 */
function checkCreateSurface(
  domain: string,
  name: string,
  list: string,
  createsInGrid: boolean,
): string[] {
  const types = readIfPresent(join(SRC_DIRECTORIES.types, `${domain}.ts`));
  if (types === null || list === "") return [];

  const created = requestFields(types, `${name}CreateRequest`);
  if (created.length === 0) return [];

  const editable = editableColumns(list);
  const rowHoldsTheRecord = created.every((field) => editable.has(field));
  if (rowHoldsTheRecord && !createsInGrid) {
    return [
      `frontend/src/sections/${domain}/${name}List.tsx: every field of ${name}CreateRequest ` +
        `(${created.join(", ")}) is an editable column, so the row is the form — create the ` +
        "row in the grid instead of in a dialog that asks for what the row already shows",
    ];
  }
  if (!rowHoldsTheRecord && createsInGrid) {
    const missing = created.filter((field) => !editable.has(field));
    return [
      `frontend/src/sections/${domain}/${name}List.tsx: creates rows in the grid, but ` +
        `${missing.join(", ")} of ${name}CreateRequest is no editable column — a draft row ` +
        "cannot carry it, so the create belongs in the dialog",
    ];
  }
  return [];
}

/** The field names of one request interface, as `types/<domain>.ts` declares them. */
function requestFields(types: string, interfaceName: string): string[] {
  const start = types.indexOf(`export interface ${interfaceName} {`);
  if (start === -1) return [];
  const end = types.indexOf("\n}", start);
  const body = types.slice(start, end === -1 ? types.length : end);
  return [...body.matchAll(/^ {2}(\w+)\??:/gm)].map((match: RegExpMatchArray) => match[1]);
}

/**
 * The columns a row can be typed into.
 *
 * A column the grid renders but never edits does not hold a field: `code` is on
 * the integration list and is read-only, because the server has no rename.
 */
function editableColumns(list: string): Set<string> {
  const fields = new Set<string>();
  // A column names its field either way: spread from the COLUMN table
  // (`...sized('email')`, the list standard) or spelled (`field: 'email'`).
  const columns = [...list.matchAll(/(?:\.\.\.sized\('|field: ')(\w+)'/g)];
  for (const [index, match] of columns.entries()) {
    const from = match.index ?? 0;
    const to = columns[index + 1]?.index ?? list.length;
    if (/editable: true/.test(list.slice(from, to))) fields.add(match[1]);
  }
  return fields;
}

function checkServiceMethods(domain: string): string[] {
  const issues: string[] = [];
  const path = join(SRC_DIRECTORIES.services, `${domain}.service.ts`);
  // existence-ok: domains are discovered from this very file, so it exists by construction.
  const content = readIfPresent(path);
  if (content === null) return issues;

  for (const method of SERVICE_METHODS) {
    if (!new RegExp(`\\b${method}\\s*:`).test(content)) {
      issues.push(
        `${label(path)}: no ${method}() — a resource service covers ` +
          `${SERVICE_METHODS.join("/")}, so a screen never builds a URL itself`,
      );
    }
  }
  return issues;
}

function checkQueryHooks(domain: string, name: string): string[] {
  const issues: string[] = [];
  const path = join(SRC_DIRECTORIES.queryHooks, `use${name}.ts`);
  // existence-ok: the presence loop above reports every missing per-domain file.
  const content = readIfPresent(path);
  if (content === null) return issues;

  const required = [
    `use${name}List`,
    `use${name}`,
    `useCreate${name}`,
    `useUpdate${name}`,
    `useDelete${name}`,
  ];
  for (const hook of required) {
    if (!new RegExp(`export function ${hook}\\b`).test(content)) {
      issues.push(`${label(path)}: no exported ${hook} — the ${domain} domain is incomplete`);
    }
  }
  return issues;
}

/** A section directory with no service is a screen wired to nothing. */
function checkOrphanSections(domains: string[]): string[] {
  const issues: string[] = [];
  if (!existsSync(SRC_DIRECTORIES.sections)) return issues;

  // domain-literal: the two screens that reach no API of their own - a session and a cross-domain overview; a wrong entry fails loudly here, it never passes silently
  const known = new Set([...domains, "auth", "dashboard"]);
  for (const entry of readdirSync(SRC_DIRECTORIES.sections, { withFileTypes: true })) {
    if (!entry.isDirectory() || known.has(entry.name)) continue;
    issues.push(
      `frontend/src/sections/${entry.name}/: no ${entry.name}.service.ts — ` +
        "a section with no service reaches the API some other way",
    );
  }
  return issues;
}

// Direct execution (make check-frontend-domain): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-domain.ts")) {
  const issues = checkFrontendDomainSync();
  console.log("==> check-frontend-domain");
  if (issues.length === 0) {
    console.log("    PASS: every frontend domain carries all 6 layers");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-domain");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
