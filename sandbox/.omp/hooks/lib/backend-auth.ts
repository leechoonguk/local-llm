// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * Domain auth checks — JWT auth + domain exception patterns (backend-auth.md).
 *
 * Validates:
 *   - every domain exception in core/exceptions.py has a handler
 *   - services raise only domain exceptions (never ValueError/RuntimeError)
 *
 * Pure validation — no ast-grep, no side effects. Called by the
 * check-backend-domain orchestrator.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

export function checkDomainAuth(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  issues.push(...checkExceptionHandlers(base));
  issues.push(...checkServiceDomainExceptions(base));
  // --- Token claims: dated on mint, required on decode ---
  // `exp` alone is not enough: a token with no `sub` authenticates nobody and a
  // token with no `iat` cannot be aged, so both are asserted where they are
  // cheapest to keep — the mint site and the decode options.
  const securityPath = join(projectRoot, "backend", "app", "core", "security.py");
  if (existsSync(securityPath)) {
    const security = readFileSync(securityPath, "utf-8");
    if (!/"iat":/.test(security)) {
      issues.push("security.py: the access token carries no `iat` — a leaked token cannot be aged");
    }
    if (!/"require":\s*\[[\s\S]{0,80}?"exp"[\s\S]{0,40}?"sub"/.test(security)) {
      issues.push(
        'security.py: jwt.decode must require ["exp", "sub"] — a token missing either ' +
          "must be rejected at the decode, not downstream",
      );
    }
  }

  return issues;
}

/**
 * Verifies the exception-handling contract: every domain exception class
 * defined in core/exceptions.py must have a matching @app.exception_handler
 * registration inside setup_exception_handler. A new exception without a
 * handler would surface as a 500 instead of a proper JSON response.
 */
function checkExceptionHandlers(base: string): string[] {
  const issues: string[] = [];
  const exceptionsPath = join(base, "core", "exceptions.py");
  if (!existsSync(exceptionsPath)) return issues;

  const content = readFileSync(exceptionsPath, "utf-8");

  // Domain exception classes: `class <Name>Error(Exception):` at module level.
  const exceptionClasses = [...content.matchAll(/^class\s+(\w+Error)\(Exception\):/gm)].map((m) => m[1]);

  for (const cls of exceptionClasses) {
    // Handler: @app.exception_handler(<Name>Error) inside setup_exception_handler.
    if (!content.includes(`@app.exception_handler(${cls})`)) {
      issues.push(
        `exceptions.py: ${cls} has no @app.exception_handler registration — ` +
          "it would surface as HTTP 500; add a handler in setup_exception_handler",
      );
    }
  }

  return issues;
}

/**
 * Verifies that services only raise domain exceptions defined in
 * core/exceptions.py (NotFoundError, ConflictError, AuthenticationError, ...).
 * A standard exception (ValueError, RuntimeError) has no exception handler
 * and would surface as HTTP 500 instead of a proper JSON response.
 *
 * Adding a new domain exception requires 3 steps (all machine-checked):
 *   1. class XxxError(Exception) in core/exceptions.py
 *   2. @app.exception_handler(XxxError) in setup_exception_handler
 *      (checked by checkExceptionHandlers)
 *   3. raise XxxError(...) in services (checked here)
 */
function checkServiceDomainExceptions(base: string): string[] {
  const issues: string[] = [];
  const exceptionsPath = join(base, "core", "exceptions.py");
  const servicesDir = join(base, "services");
  if (!existsSync(exceptionsPath) || !existsSync(servicesDir)) return issues;

  // Domain exception classes: `class <Name>Error(Exception):` at module level.
  const exceptionsContent = readFileSync(exceptionsPath, "utf-8");
  const domainExceptions = new Set(
    [...exceptionsContent.matchAll(/^class\s+(\w+Error)\(Exception\):/gm)].map((m) => m[1]),
  );

  for (const f of readdirSync(servicesDir)) {
    if (!f.endsWith(".py") || f === "__init__.py") continue;
    const content = readFileSync(join(servicesDir, f), "utf-8");
    for (const m of content.matchAll(/\braise\s+(\w+Error)\s*\(/g)) {
      const exc = m[1];
      if (!domainExceptions.has(exc)) {
        issues.push(
          `${f}: raises "${exc}" which is not a domain exception — ` +
            `define it in core/exceptions.py + register a handler, or use an existing domain exception`,
        );
      }
    }
  }

  return issues;
}
