import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import {
  SRC_DIRECTORIES,
  discoverDomains,
  frontendSrc,
  label,
  pascalCase,
  readIfPresent,
} from "../lib/frontend-source.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

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
 *   pages/<Domain>Page.tsx   the route component
 *
 * A half-built domain is the failure this prevents: a service with no hook is
 * called from a screen directly, and a screen with no page is unreachable.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

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
    issues.push(...checkLayerFiles(domain, name));
    issues.push(...checkServiceMethods(domain));
    issues.push(...checkQueryHooks(domain, name));

    if (!new RegExp(`${domain.toUpperCase()}_ENDPOINTS\\s*=`).test(endpoints)) {
      issues.push(
        `frontend/src/lib/api/endpoints.ts: no ${domain.toUpperCase()}_ENDPOINTS — ` +
          `the ${domain} service would carry its URLs inline`,
      );
    }
    if (!new RegExp(`${domain}Keys\\s*=\\s*createQueryKeys`).test(queryKeys)) {
      issues.push(
        `frontend/src/lib/api/queryKeys.ts: no ${domain}Keys — ` +
          `the ${domain} hooks cannot share an invalidation key`,
      );
    }
  }

  issues.push(...checkOrphanSections(domains));
  return issues;
}

/** Every layer that is one file per domain. */
function checkLayerFiles(domain: string, name: string): string[] {
  const issues: string[] = [];
  const required = [
    join(SRC_DIRECTORIES.types, `${domain}.ts`),
    join(SRC_DIRECTORIES.queryHooks, `use${name}.ts`),
    join(SRC_DIRECTORIES.sections, domain, `${name}List.tsx`),
    join(SRC_DIRECTORIES.sections, domain, `${name}FormDialog.tsx`),
    join(SRC_DIRECTORIES.pages, `${name}Page.tsx`),
  ];
  for (const path of required) {
    if (!existsSync(path)) {
      issues.push(`${label(path)}: missing — the ${domain} domain is incomplete`);
    }
  }
  return issues;
}

function checkServiceMethods(domain: string): string[] {
  const issues: string[] = [];
  const path = join(SRC_DIRECTORIES.services, `${domain}.service.ts`);
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
