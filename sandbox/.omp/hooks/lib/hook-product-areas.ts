/**
 * The navigation's areas, and the one pattern each of them carries.
 *
 * Membership is not declared here: it is read from `NAV_GROUPS`, the product's
 * own statement of what belongs together and the same list
 * `check-frontend-routing` compares against the path registry. What is declared
 * here is the mapping from a group to a pattern, and the one word per
 * operations domain that a pattern cannot derive — the name of the child
 * collection its executions are logged into.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { resolveProjectRoot } from "./hook-project-root.ts";

export type AreaPattern = "record" | "operations" | "derived";

/** Nav group subheader → the pattern every domain in that group carries. */
export const AREA_PATTERNS: Record<string, AreaPattern> = {
  "group.user": "record",
  "group.batch": "operations",
  "group.food": "derived",
};

export interface ExecutionLog {
  /** The router's child collection: `GET /{id}/<collection>`. */
  collection: string;
  /** The query hook that reads it, in `lib/api/hooks/use<Domain>.ts`. */
  hook: string;
}

/**
 * Where an operations domain's executions are logged, and what reads them.
 *
 * Declared rather than derived: the collection differs per domain (`runs`,
 * `calls`) and the hook follows the API layer's own naming
 * (`use<Domain><Row>List`), while the leg does not differ at all. A domain in
 * the area with no entry here is the defect this file exists to name —
 * `integration` stood in the area with its `integration_call` rows written on
 * every call and readable by nothing.
 */
export const EXECUTION_LOG: Record<string, ExecutionLog> = {
  batch: { collection: "runs", hook: "useBatchRunList" },
  integration: { collection: "calls", hook: "useIntegrationCallList" },
};

export interface NavEntry {
  /** The nav group's subheader key, or `null` for the ungrouped head. */
  group: string | null;
  /** `titleKey` — also the i18n key the sidebar renders. */
  title: string;
  /** First path segment: the domain's directory under `sections/`. */
  domain: string;
}

const NAV_FILE = join(
  resolveProjectRoot(),
  "frontend", "src", "layouts", "dashboard", "config-navigation.tsx",
);

/**
 * Every navigation entry with the group it stands under.
 *
 * Parsed from the source rather than imported: a hook runs under Node with no
 * bundler, and the file imports `PATHS` and the icon registry. The shape read
 * is the one the file's own type declares — `subheaderKey`, then `titleKey` and
 * `path` per item — so a rename of either breaks the parse loudly instead of
 * returning an empty list. An empty result is reported by the caller as an
 * unreadable navigation, never as "no areas to check".
 */
export function navEntries(): NavEntry[] {
  if (!existsSync(NAV_FILE)) return [];
  const source = readFileSync(NAV_FILE, "utf-8");
  const start = source.indexOf("export const NAV_GROUPS");
  if (start === -1) return [];
  const entries: NavEntry[] = [];
  let group: string | null = null;
  for (const line of source.slice(start).split("\n")) {
    const subheader = /subheaderKey:\s*'([^']+)'/.exec(line);
    if (subheader !== null) {
      group = subheader[1];
      continue;
    }
    const title = /titleKey:\s*'([^']+)'/.exec(line);
    const path = /path:\s*PATHS\.([\w.]+)/.exec(line);
    if (title === null) continue;
    entries.push({ group, title: title[1], domain: (path?.[1] ?? title[1]).split(".")[0] });
  }
  return entries;
}

/** The pattern a nav entry answers to, or `null` when its group declares none. */
export function patternOf(entry: NavEntry): AreaPattern | null {
  if (entry.group === null) return null;
  return AREA_PATTERNS[entry.group] ?? null;
}
