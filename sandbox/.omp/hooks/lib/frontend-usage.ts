/**
 * Reachability from a screen — the layer the route-coverage check was missing.
 *
 * Coverage stopped at the transport layer: a route counted as called when a
 * service function named it, whether or not anything above that function used
 * it. Measured consequence — the frontend has no operation feature at all, and
 * `POST /integration/{id}/operations/{op}/execute` still looked covered, because
 * `integrationService.execute` and `useExecuteOperation` existed and nothing
 * rendered them.
 *
 * So the chain is what matters: **service function → query hook → screen**. A
 * link that nothing above it uses is dead code, and a route reached only through
 * dead code is not reached.
 *
 * `auth` is the documented exception: a session is not a query domain, so
 * `authService` is consumed by `auth/JwtContext.tsx` rather than by a hook.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

export interface UsageGraph {
  /** `integrationService.execute` → the hook files that call it. */
  serviceUsers: Map<string, string[]>;
  /** `useIntegrationList` → the files outside `lib/api/` that use it. */
  hookUsers: Map<string, string[]>;
  /** Service functions a screen can reach through some hook. */
  reachable: Set<string>;
}

const SERVICE_FUNCTION = /^ {2}(\w+):/gm;

const HOOK_EXPORT = /^export function (\w+)/gm;

/** A session is consumed by the auth context, not by a query hook. */
// domain-literal: a session is not a resource, so it has no query hook to find
const CONTEXT_CONSUMERS = ["auth"];

export function buildUsageGraph(frontendSrc: string): UsageGraph {
  const servicesDirectory = join(frontendSrc, "lib", "api", "services");
  const hooksDirectory = join(frontendSrc, "lib", "api", "hooks");

  const hookFiles = listFiles(hooksDirectory);
  const outsideApi = listFiles(frontendSrc, join(frontendSrc, "lib", "api"));

  const serviceUsers = new Map<string, string[]>();
  const hookOwners = new Map<string, string[]>();
  for (const file of listFiles(servicesDirectory)) {
    const domain = basename(file).replace(".service.ts", "");
    const service = `${domain}Service`;
    const source = readFileSync(file, "utf-8");
    SERVICE_FUNCTION.lastIndex = 0;
    for (const match of source.matchAll(SERVICE_FUNCTION)) {
      const symbol = `${service}.${match[1]}`;
      const users = CONTEXT_CONSUMERS.includes(domain)
        ? outsideApi.filter((path: string) => readFileSync(path, "utf-8").includes(symbol))
        : hookFiles.filter((path: string) => readFileSync(path, "utf-8").includes(symbol));
      serviceUsers.set(symbol, users);
      for (const user of users) {
        hookOwners.set(user, [...(hookOwners.get(user) ?? []), symbol]);
      }
    }
  }

  const hookUsers = new Map<string, string[]>();
  const reachable = new Set<string>();
  for (const file of hookFiles) {
    const source = readFileSync(file, "utf-8");
    HOOK_EXPORT.lastIndex = 0;
    for (const match of source.matchAll(HOOK_EXPORT)) {
      const hook = match[1];
      const users = outsideApi.filter((path: string) =>
        new RegExp(`\\b${hook}\\b`).test(readFileSync(path, "utf-8")),
      );
      hookUsers.set(hook, users);
      if (users.length === 0) continue;
      // The hook is rendered, so every service function its body calls is reached.
      for (const symbol of hookOwners.get(file) ?? []) {
        if (bodyOf(source, hook).includes(symbol)) reachable.add(symbol);
      }
    }
  }

  // A context consumer is a screen-side file already, so its calls are reached.
  for (const [symbol, users] of serviceUsers) {
    const domain = symbol.replace(/Service\..*/, "");
    if (CONTEXT_CONSUMERS.includes(domain) && users.length > 0) reachable.add(symbol);
  }

  return { serviceUsers, hookUsers, reachable };
}

/**
 * The text of one exported hook, up to the next export.
 *
 * The `(` matters: `useUser` is a prefix of `useUserList`, so an `indexOf` on
 * the bare name read the wrong body and reported every `detail` hook as
 * unreachable.
 */
function bodyOf(source: string, hook: string): string {
  const start = source.indexOf(`export function ${hook}(`);
  if (start === -1) return "";
  const next = source.indexOf("\nexport function ", start + 1);
  return source.slice(start, next === -1 ? source.length : next);
}

function listFiles(directory: string, exclude?: string): string[] {
  const files: string[] = [];
  const walk = (current: string): void => {
    let entries: string[];
    try {
      entries = readdirSync(current);
    } catch {
      return;
    }
    for (const entry of entries) {
      const path = join(current, entry);
      if (exclude !== undefined && path.startsWith(exclude)) continue;
      if (statSync(path).isDirectory()) {
        walk(path);
        continue;
      }
      if (path.endsWith(".ts") || path.endsWith(".tsx")) files.push(path);
    }
  };
  walk(directory);
  return files;
}

function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1];
}
