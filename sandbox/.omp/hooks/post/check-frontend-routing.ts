import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import {
  SRC_DIRECTORIES,
  frontendSrc,
  readIfPresent,
  readSources,
} from "../lib/frontend-source.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-Routing Post Hook
 *
 * Validates the routing contract from .omp/rules/frontend-routing.md:
 *
 *   1. registry ↔ route table, both ways — every PATHS leaf is routed and every
 *      route comes from PATHS (a literal path is a link that breaks silently)
 *   2. registry ↔ navigation — every authenticated route is reachable from the
 *      sidebar, and the sidebar points at nothing unrouted
 *   3. no literal `to="/..."` / `navigate('/...')` anywhere in src
 *   4. guards live in the layouts, so a page cannot forget one
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/**
 * Registry leaves that are not navigation targets: the root only redirects, and
 * the login route lives outside the authenticated shell.
 */
const NON_NAV_PATHS: Record<string, true> = { root: true, "auth.login": true };

export default function checkFrontendRouting(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-routing", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendRoutingSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-routing");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-routing",
      issues,
      "run make check-frontend-routing for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-routing") };
  }));
}

export function checkFrontendRoutingSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  const paths = readIfPresent(join(SRC_DIRECTORIES.routes, "paths.ts"));
  const routes = readIfPresent(join(frontendSrc, "App.tsx"));
  const navigation = readIfPresent(join(SRC_DIRECTORIES.layouts, "dashboard", "config-navigation.tsx"));

  if (paths === null) return ["frontend/src/routes/paths.ts: missing — routes would be literals"];
  if (routes === null) return ["frontend/src/App.tsx: missing — the app has no route table"];
  if (navigation === null) {
    return ["frontend/src/layouts/dashboard/config-navigation.tsx: missing — no navigation model"];
  }

  const registry = registryLeaves(paths);
  const routed = referencedLeaves(routes);
  const navigated = referencedLeaves(navigation);

  for (const leaf of registry) {
    if (!routed.has(leaf)) {
      issues.push(
        `frontend/src/App.tsx: PATHS.${leaf} is registered but not routed — the path ` +
          "exists and reaches nothing",
      );
    }
    if (NON_NAV_PATHS[leaf] !== true && !navigated.has(leaf)) {
      issues.push(
        `frontend/src/layouts/dashboard/config-navigation.tsx: PATHS.${leaf} is routed but ` +
          "absent from NAV_ITEMS — the screen is unreachable from the sidebar",
      );
    }
  }
  for (const leaf of navigated) {
    if (!registry.has(leaf)) {
      issues.push(
        `frontend/src/layouts/dashboard/config-navigation.tsx: PATHS.${leaf} is not in the ` +
          "registry — the sidebar points at a path that does not exist",
      );
    }
  }

  issues.push(...checkLiteralPaths());
  issues.push(...checkGuards());
  return issues;
}

/** `dashboard: '/dashboard'` and `auth: { login: '...' }` → `dashboard`, `auth.login`. */
function registryLeaves(source: string): Set<string> {
  const leaves = new Set<string>();
  let group: string | null = null;
  for (const line of source.split("\n")) {
    const nested = /^\s{2}(\w+):\s*\{\s*$/.exec(line);
    if (nested !== null) {
      group = nested[1];
      continue;
    }
    if (/^\s{2}\},?\s*$/.test(line)) {
      group = null;
      continue;
    }
    const leaf = /^\s+(\w+):\s*[`'"]/.exec(line);
    if (leaf !== null) {
      leaves.add(group === null ? leaf[1] : `${group}.${leaf[1]}`);
    }
  }
  return leaves;
}

function referencedLeaves(source: string): Set<string> {
  return new Set(
    [...source.matchAll(/PATHS\.([\w.]+)/g)].map((match: RegExpMatchArray) => match[1]),
  );
}

/** A path spelled in a component is the one the router will not rename. */
function checkLiteralPaths(): string[] {
  const issues: string[] = [];
  const registry = join(SRC_DIRECTORIES.routes, "paths.ts");
  for (const file of readSources(frontendSrc)) {
    if (file.path === registry) continue;
    file.content.split("\n").forEach((line: string, index: number) => {
      if (/\bto=["']\//.test(line) || /navigate\(\s*['"]\//.test(line)) {
        issues.push(
          `${file.label}:${index + 1}: literal route — use PATHS from ` +
            "frontend/src/routes/paths.ts",
        );
      }
      if (/\bpath=["']\/(?!\*)/.test(line)) {
        issues.push(
          `${file.label}:${index + 1}: literal route path — bind the route to PATHS so the ` +
            "registry and the table cannot disagree",
        );
      }
    });
  }
  return issues;
}

/**
 * The guard belongs to the layout: put it in a page and the next page added to
 * the same layout is unprotected with no diff to notice.
 */
function checkGuards(): string[] {
  const issues: string[] = [];
  const guarded: Record<string, string> = {
    "dashboard/DashboardLayout.tsx": "AuthGuard",
    "auth/AuthLayout.tsx": "GuestGuard",
  };
  for (const [file, guard] of Object.entries(guarded)) {
    const content = readIfPresent(join(SRC_DIRECTORIES.layouts, file));
    if (content === null) {
      issues.push(`frontend/src/layouts/${file}: missing — the guard has no home`);
      continue;
    }
    if (!new RegExp(`<${guard}>`).test(content)) {
      issues.push(`frontend/src/layouts/${file}: does not wrap its outlet in <${guard}>`);
    }
  }
  for (const file of readSources(SRC_DIRECTORIES.pages)) {
    if (/<AuthGuard>|<GuestGuard>/.test(file.content)) {
      issues.push(
        `${file.label}: guards a page — move it to the layout, or the next page added ` +
          "beside this one is unprotected",
      );
    }
  }
  return issues;
}

// Direct execution (make check-frontend-routing): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-routing.ts")) {
  const issues = checkFrontendRoutingSync();
  console.log("==> check-frontend-routing");
  if (issues.length === 0) {
    console.log("    PASS: routes, registry and navigation agree");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-routing");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
