/**
 * A service composes repositories. It never composes another service.
 *
 * The invariant is one import: nothing in `services/*.py` imports from
 * `app.services`. That single check covers both the typed-parameter form
 * (`def __init__(self, session, other: OtherService)`) and the untyped
 * construction form (`self.other = OtherService(session)`) — neither is
 * possible without importing the class first.
 *
 * Why: this repo's services each own their transaction (`async with
 * self.session.begin(): ...`). A service holding another service could call a
 * method that opens a *second* `session.begin()` on the same session mid-call,
 * or run business logic through two owners with no single place a reader
 * checks for the transaction boundary. A service composes repositories — as
 * many as the use case needs — and repositories do not begin transactions.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

const projectRoot = existsSync(join(process.cwd(), "backend", "app"))
  ? process.cwd()
  : join(process.cwd(), "..");

const SERVICES_DIR = join(projectRoot, "backend", "app", "services");

const SERVICE_IMPORT = /^\s*(?:from\s+app\.services(?:\.\w+)?\s+import\s+\w|import\s+app\.services\b)/m;

export function checkServiceInjectionSync(): string[] {
  if (!existsSync(SERVICES_DIR)) return [];
  const issues: string[] = [];
  for (const file of readdirSync(SERVICES_DIR).sort()) {
    if (!file.endsWith(".py") || file === "__init__.py") continue;
    const content = readFileSync(join(SERVICES_DIR, file), "utf-8");
    const match = SERVICE_IMPORT.exec(content);
    if (match !== null) {
      issues.push(
        `services/${file}: imports from app.services (${match[0].trim()}) — a service ` +
          "composes repositories, never another service (backend-service-injection.md)",
      );
    }
  }
  return issues;
}
