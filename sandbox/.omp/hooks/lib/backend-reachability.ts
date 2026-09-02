// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * What in `backend/app/` is reachable from something that can actually run.
 *
 * The frontend has this shape already: `check-frontend-contract` refuses a
 * service function no hook calls and a hook no screen renders, because "a
 * feature that was never built" looks exactly like a finished one from inside
 * its own layer. The backend had no counterpart, so the same shape survived
 * here: two `*ServiceDep` aliases nobody injected, kept alive by a rule that
 * demanded one per domain.
 *
 * An entry point is what the outside world can start: a router endpoint, a
 * scheduled batch job, or the lifespan. Tests do not count — that is the whole
 * point of the check, and it is why the frontend version reads screens rather
 * than test files.
 */

/** The layers whose public surface must be reachable. */
const CALLABLE_LAYERS = ["services", "repositories"] as const;

/**
 * Methods the 5-layer template requires of every domain (rule://backend-domain),
 * whether or not that domain publishes a router. They are the table's access
 * surface, not a feature someone forgot to wire, so their existence is
 * explained by the template and this check leaves them alone. Anything beyond
 * them was written for a reason, and an unreachable reason never landed.
 */
const TEMPLATE_METHOD = /^(get|list|create|update|delete)(_\w+)?$/;

export interface DeadSurface {
  label: string;
  detail: string;
}

export function collectBackendReachability(projectRoot: string): DeadSurface[] {
  const app = join(projectRoot, "backend", "app");
  if (!existsSync(app)) return [];

  const sources = new Map<string, string>();
  collectPython(app, app, sources);

  return [...checkDeadAliases(sources), ...checkDeadMethods(sources)];
}

/**
 * A `*ServiceDep` alias is `Annotated[X, Depends(...)]`, and only an endpoint
 * signature can consume one. Declared without a caller it is the backend's
 * "endpoint constant declared and never called": a wire to a socket that was
 * never installed.
 */
function checkDeadAliases(sources: Map<string, string>): DeadSurface[] {
  const dead: DeadSurface[] = [];
  const depsPath = "dependencies/services.py";
  const deps = sources.get(depsPath);
  if (deps === undefined) return dead;

  for (const match of deps.matchAll(/^(\w+Dep)\s*=\s*Annotated\[/gm)) {
    const alias = match[1];
    const used = [...sources].some(
      ([path, content]) => path !== depsPath && new RegExp(`\\b${alias}\\b`).test(content),
    );
    if (used) continue;
    dead.push({
      label: `app/${depsPath}`,
      detail:
        `${alias} is declared and injected nowhere — a DI alias is read by an endpoint ` +
        "signature and nothing else, so one without a router is a wire to no socket",
    });
  }
  return dead;
}

/**
 * A public method beyond the template with no caller anywhere in `app/`.
 *
 * Matched as `.name` rather than `.name(`: a `@property` is read without
 * parentheses (`service.last_call_id`), and demanding the call form reported
 * every property in the tree as dead.
 */
function checkDeadMethods(sources: Map<string, string>): DeadSurface[] {
  const dead: DeadSurface[] = [];
  for (const [path, content] of sources) {
    if (!CALLABLE_LAYERS.some((layer) => path.startsWith(`${layer}/`))) continue;
    for (const match of content.matchAll(/^ {4}(?:async )?def ([a-z]\w*)\(/gm)) {
      const method = match[1];
      if (method.startsWith("_") || TEMPLATE_METHOD.test(method)) continue;
      const used = [...sources].some(
        ([other, source]) => other !== path && new RegExp(`\\.${method}\\b`).test(source),
      );
      if (used) continue;
      dead.push({
        label: `app/${path}`,
        detail:
          `${method} is called by nothing in app/ — a method beyond the CRUD template was ` +
          "written for a purpose, and one no entry point can reach is a purpose that never landed",
      });
    }
  }
  return dead;
}

function collectPython(root: string, directory: string, into: Map<string, string>): void {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      collectPython(root, path, into);
      continue;
    }
    if (!entry.name.endsWith(".py") || entry.name === "__init__.py") continue;
    into.set(path.slice(root.length + 1), readFileSync(path, "utf-8"));
  }
}
