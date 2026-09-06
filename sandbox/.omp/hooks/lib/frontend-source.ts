/**
 * Frontend source discovery — shared by every `check-frontend-*` hook.
 *
 * One module owns "what files exist and what a domain is", so six hooks cannot
 * disagree about which tree they are checking. Everything here is read-only and
 * pure: the hooks decide what is a violation, this decides what to look at.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join, relative, sep } from "node:path";

/** Extensions the frontend standard governs. */
const SOURCE_EXTENSIONS = [".ts", ".tsx"];

/** Directories inside `src/` that belong to a tool, not to the standard. */
const SKIPPED_DIRECTORIES: Record<string, true> = { node_modules: true, dist: true };

/**
 * `auth` has a service and a query key, but it is a session, not a resource:
 * there is no list, no CRUD dialog and no navigation entry to require.
 */
const NON_RESOURCE_DOMAINS: Record<string, true> = { auth: true };

export interface SourceFile {
  /** Absolute path. */
  path: string;
  /** Repository-relative label for a warning line. */
  label: string;
  content: string;
}

export const projectRoot = existsSync(join(process.cwd(), "frontend", "src"))
  ? process.cwd()
  : join(process.cwd(), "..");

export const frontendSrc = join(projectRoot, "frontend", "src");

/**
 * The frontend layout — what may exist directly under `frontend/src/`.
 *
 * The backend twin (`backend-layout.ts`) also constrains depth, because flat
 * layer scans went blind when domains became folders. Here the read side
 * (`walkSources`) is fully recursive, so depth blinds nothing and only the
 * directory set is declared: the write gate refuses a new top-level directory
 * (`frontend/src/adapters/`) the way `strict-backend-app-structure` refuses
 * `backend/app/adapters/`.
 */
export const SRC_LAYOUT = {
  directories: {
    auth: true,
    components: true,
    hooks: true,
    layouts: true,
    lib: true,
    locales: true,
    pages: true,
    routes: true,
    sections: true,
    theme: true,
    types: true,
    utils: true,
  } as Record<string, true>,
  rootFiles: {
    "App.tsx": true,
    "main.tsx": true,
    "config.ts": true,
    "styles.css": true,
    "vite-env.d.ts": true,
  } as Record<string, true>,
};

export const SRC_DIRECTORIES = {
  components: join(frontendSrc, "components"),
  hooks: join(frontendSrc, "hooks"),
  layouts: join(frontendSrc, "layouts"),
  lib: join(frontendSrc, "lib", "api"),
  locales: join(frontendSrc, "locales"),
  pages: join(frontendSrc, "pages"),
  routes: join(frontendSrc, "routes"),
  sections: join(frontendSrc, "sections"),
  services: join(frontendSrc, "lib", "api", "services"),
  queryHooks: join(frontendSrc, "lib", "api", "hooks"),
  types: join(frontendSrc, "types"),
} as const;

export function walkSources(root: string): string[] {
  if (!existsSync(root)) return [];
  const files: string[] = [];
  const stack = [root];
  while (stack.length > 0) {
    const dir = stack.pop()!;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (SKIPPED_DIRECTORIES[entry.name] !== true) stack.push(join(dir, entry.name));
      } else if (SOURCE_EXTENSIONS.some((ext: string) => entry.name.endsWith(ext))) {
        files.push(join(dir, entry.name));
      }
    }
  }
  return files.sort();
}

export function readSources(root: string): SourceFile[] {
  return walkSources(root).map((path: string) => ({
    path,
    label: label(path),
    content: readFileSync(path, "utf-8"),
  }));
}

export function label(path: string): string {
  return relative(projectRoot, path).split(sep).join("/");
}

export function readIfPresent(path: string): string | null {
  return existsSync(path) ? readFileSync(path, "utf-8") : null;
}

/**
 * Source with comments removed — the first step of every structural read.
 *
 * A check that scans raw source matches the prose explaining the construct as
 * readily as the construct: a style assertion here once passed against a file
 * whose style had been deleted, because the comment above it still named the
 * property. Both JSX (`{/* … *\/}`) and plain block comments go, then whole-line
 * `//` — a trailing `//` is left alone, since stripping it would need the string
 * tracking the callers do for themselves.
 */
export function stripComments(content: string): string {
  return content
    .replace(/\{\/\*[\s\S]*?\*\/\}|\/\*[\s\S]*?\*\//g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");
}

/**
 * A domain is a `<name>.service.ts`: the service is the layer that cannot be
 * skipped, so it is the only honest place to enumerate domains from. Session
 * services are excluded — see `NON_RESOURCE_DOMAINS`.
 */
export function discoverDomains(): string[] {
  if (!existsSync(SRC_DIRECTORIES.services)) return [];
  return readdirSync(SRC_DIRECTORIES.services)
    .filter((file: string) => file.endsWith(".service.ts"))
    .map((file: string) => file.replace(/\.service\.ts$/, ""))
    .filter((name: string) => NON_RESOURCE_DOMAINS[name] !== true)
    .sort();
}

/** `user` → `User`, `integration` → `Integration`. */
export function pascalCase(domain: string): string {
  return domain
    .split(/[-_]/)
    .map((part: string) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}
