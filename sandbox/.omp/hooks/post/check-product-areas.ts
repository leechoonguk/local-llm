/**
 * Check-Product-Areas Post Hook
 *
 * Validates product-areas.md: the navigation's three areas each carry one
 * screen pattern, and every domain standing in an area carries that pattern's
 * legs — across both halves of the stack, because the leg that was missing was
 * a backend read and a frontend surface at once.
 *
 * Cross-cutting by name (no scope prefix): it reads the navigation, the section
 * screens, the frontend API layer and the routers, because an area is a claim
 * about a domain, not about a file.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { passLine } from "../lib/hook-dormancy.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";
import { EXECUTION_LOG, navEntries, patternOf } from "../lib/hook-product-areas.ts";
import type { ExecutionLog, NavEntry } from "../lib/hook-product-areas.ts";

const projectRoot = resolveProjectRoot();
const sectionsDir = join(projectRoot, "frontend", "src", "sections");
const routersDir = join(projectRoot, "backend", "app", "routers");
const apiDir = join(projectRoot, "frontend", "src", "lib", "api");

export default function checkProductAreas(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-product-areas", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["frontend/", "backend/"])) return;

    const issues = checkProductAreasSync();
    if (issues.length === 0) {
      resetSuppression("check-product-areas");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-product-areas",
      issues,
      "run make check-product-areas for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-product-areas") };
  }));
}

export function checkProductAreasSync(): string[] {
  const entries = navEntries();
  if (entries.length === 0) {
    return [
      "frontend/src/layouts/dashboard/config-navigation.tsx: NAV_GROUPS could not be read — " +
        "area membership comes from the navigation, so an unreadable list turns every area " +
        "check off rather than passing it",
    ];
  }
  const issues: string[] = [];
  issues.push(...checkGroupsDeclareAPattern(entries));
  for (const entry of entries) {
    const pattern = patternOf(entry);
    if (pattern === null) continue;
    const lists = listFiles(entry.domain);
    // A nav item with no list screen is its own screen type (the food chat is an
    // SSE conversation): the area's pattern has nothing to bind to.
    if (lists.length === 0) continue;
    if (pattern === "record") issues.push(...checkRecordArea(entry, lists));
    if (pattern === "operations") issues.push(...checkOperationsArea(entry, lists));
    if (pattern === "derived") issues.push(...checkDerivedArea(entry, lists));
  }
  return [...new Set(issues)];
}

/**
 * Every group a nav entry stands under maps to a pattern.
 *
 * The ungrouped head is exempt by construction (`patternOf` answers `null` for
 * it), which is where the dashboard lives. A *named* group with no pattern is
 * the failure: its screens would answer to nothing while looking grouped.
 */
function checkGroupsDeclareAPattern(entries: NavEntry[]): string[] {
  const issues: string[] = [];
  for (const group of new Set(entries.map((entry: NavEntry) => entry.group))) {
    if (group === null) continue;
    const members = entries.filter((entry: NavEntry) => entry.group === group);
    if (members.some((entry: NavEntry) => patternOf(entry) !== null)) continue;
    issues.push(
      `frontend/src/layouts/dashboard/config-navigation.tsx: nav group '${group}' has no pattern in ` +
        ".omp/hooks/lib/hook-product-areas.ts (AREA_PATTERNS) — an area nobody assigned a pattern to is " +
        "an area whose screens answer to nothing (product-areas.md, The Three Areas)",
    );
  }
  return issues;
}

/** The record *is* the row: no dialog asks again, and no click opens it. */
function checkRecordArea(entry: NavEntry, lists: string[]): string[] {
  const issues: string[] = [];
  const dialogs = sectionFiles(entry.domain).filter((file: string) => file.endsWith("FormDialog.tsx"));
  if (dialogs.length > 0) {
    issues.push(
      `frontend/src/sections/${entry.domain}/${dialogs[0]}: the record area creates in the row, so a ` +
        "form dialog asks for what the row already holds (product-areas.md, Pattern: record)",
    );
  }
  for (const list of lists) {
    const content = readFileSync(join(sectionsDir, entry.domain, list), "utf-8");
    if (!/editable:\s*true/.test(content)) {
      issues.push(
        `frontend/src/sections/${entry.domain}/${list}: the record area edits in the row, but no column ` +
          "is editable (product-areas.md, Pattern: record)",
      );
    }
    if (/onRowClick=/.test(content)) {
      issues.push(
        `frontend/src/sections/${entry.domain}/${list}: a row that opens a record cannot also be the row ` +
          "that record is typed into (product-areas.md, Pattern: record)",
      );
    }
  }
  return issues;
}

/**
 * Configuration, an exercise verb, and a log of what the exercises did.
 *
 * The third leg is the reason this check exists: every file-level check passed
 * while `integration_call` was written on each call and read by nothing.
 */
function checkOperationsArea(entry: NavEntry, lists: string[]): string[] {
  const issues: string[] = [];
  const domain = entry.domain;
  for (const list of lists) {
    const content = readFileSync(join(sectionsDir, domain, list), "utf-8");
    if (!/editable:\s*true/.test(content)) {
      issues.push(
        `frontend/src/sections/${domain}/${list}: an operations row is configuration edited in place, but ` +
          "no column is editable (product-areas.md, Pattern: operations)",
      );
    }
    if (!/onRowClick=/.test(content)) {
      issues.push(
        `frontend/src/sections/${domain}/${list}: the row is the door to this domain's log surface, and it ` +
          "opens nothing (product-areas.md, Pattern: operations)",
      );
    }
    if (/actions\.(view|history)'/.test(content)) {
      issues.push(
        `frontend/src/sections/${domain}/${list}: a view/history button beside a row that is already the ` +
          "door to the same surface — one intent, one control (product-areas.md, Pattern: operations)",
      );
    }
  }
  const routerPath = join(routersDir, `${domain}.py`);
  if (!existsSync(routerPath)) {
    issues.push(
      `backend/app/routers/${domain}.py: an operations domain with no router — its exercise verb and its ` +
        "log have nowhere to live (product-areas.md, Pattern: operations)",
    );
    return issues;
  }
  const router = readFileSync(routerPath, "utf-8");
  // A POST on the row, not on the collection: `POST /` creates configuration,
  // `POST /{id}/…` is the verb that makes it happen now.
  if (!/@router\.post\(\s*"\/\{/.test(router)) {
    issues.push(
      `backend/app/routers/${domain}.py: no exercise verb (POST on the row) — a configuration nobody can ` +
        "try is a configuration nobody can trust (product-areas.md, Pattern: operations)",
    );
  }
  const log = EXECUTION_LOG[domain];
  if (log === undefined) {
    issues.push(
      `.omp/hooks/lib/hook-product-areas.ts: ${domain} stands in the operations area with no EXECUTION_LOG entry — ` +
        "declare the child collection its executions are logged into (product-areas.md, Adding A Domain)",
    );
    return issues;
  }
  if (!new RegExp(`@router\\.get\\(\\s*"/\\{[^"]*/${log.collection}"`).test(router)) {
    issues.push(
      `backend/app/routers/${domain}.py: no GET on {id}/${log.collection} — the executions are written and never read, so ` +
        "the product cannot answer what this configuration did (product-areas.md, Pattern: operations)",
    );
  }
  issues.push(...checkLogIsReachable(domain, log));
  return issues;
}

/** The log a router exposes is read by the frontend and shown by a screen. */
function checkLogIsReachable(domain: string, log: ExecutionLog): string[] {
  const issues: string[] = [];
  const endpoints = readIfPresent(join(apiDir, "endpoints.ts"));
  if (endpoints !== null && !new RegExp(`/\\$\\{id\\}/${log.collection}`).test(endpoints)) {
    issues.push(
      `frontend/src/lib/api/endpoints.ts: no ${domain} ${log.collection} path — the log endpoint exists and no ` +
        "client reads it (product-areas.md, Pattern: operations)",
    );
  }
  const hooks = readIfPresent(join(apiDir, "hooks", `use${pascal(domain)}.ts`));
  if (hooks !== null && !new RegExp(`export function ${log.hook}\\b`).test(hooks)) {
    issues.push(
      `frontend/src/lib/api/hooks/use${pascal(domain)}.ts: no ${log.hook} — a surface cannot show what ` +
        "nothing fetches (product-areas.md, Pattern: operations)",
    );
  }
  // The hook's *call*, not the collection's word: prose about calls matched a
  // screen that showed none (measured while writing this check).
  const shown = sectionFiles(domain).some((file: string) =>
    new RegExp(`\\b${log.hook}\\(`).test(readFileSync(join(sectionsDir, domain, file), "utf-8")),
  );
  if (!shown) {
    issues.push(
      `frontend/src/sections/${domain}/: no screen shows the ${log.collection} log — the row is a door to a ` +
        "surface that does not exist (product-areas.md, Pattern: operations)",
    );
  }
  return issues;
}

/** A read-only area's lists say so in their own file names. */
function checkDerivedArea(entry: NavEntry, lists: string[]): string[] {
  return lists
    .filter((list: string) => !list.endsWith("DerivedList.tsx"))
    .map((list: string) =>
      `frontend/src/sections/${entry.domain}/${list}: the derived area is rebuilt from the ledgers, so its ` +
        "lists are *DerivedList.tsx — a plain list is a writable screen in a read-only area " +
        "(product-areas.md, Pattern: derived)",
    );
}

/** A domain's list screens — the area's pattern binds to these. */
function listFiles(domain: string): string[] {
  return sectionFiles(domain).filter(
    (file: string) => file.endsWith("List.tsx") && !file.includes("/"),
  );
}

/**
 * Every screen of a domain, including the ones under `detail/`.
 *
 * A domain's record surface lives in a subdirectory (`integration/detail/`), so
 * a flat read answered "no screen shows the log" while the tab that shows it sat
 * one directory down — measured on exactly that file.
 */
function sectionFiles(domain: string): string[] {
  const dir = join(sectionsDir, domain);
  if (!existsSync(dir)) return [];
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      files.push(
        ...readdirSync(join(dir, entry.name))
          .filter((file: string) => file.endsWith(".tsx"))
          .map((file: string) => join(entry.name, file)),
      );
      continue;
    }
    if (entry.name.endsWith(".tsx")) files.push(entry.name);
  }
  return files;
}

function readIfPresent(path: string): string | null {
  return existsSync(path) ? readFileSync(path, "utf-8") : null;
}

function pascal(domain: string): string {
  return domain.replace(/(^|_)(\w)/g, (_match: string, _sep: string, char: string) => char.toUpperCase());
}

// Direct execution (make check-product-areas): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-product-areas.ts")) {
  const issues = checkProductAreasSync();
  console.log("==> check-product-areas");
  if (issues.length === 0) {
    console.log(passLine("check-product-areas", "every nav area carries its pattern's legs"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-product-areas");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
