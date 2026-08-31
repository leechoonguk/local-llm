// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * Core exception policy — cross-file half (backend-exceptions.md).
 *
 * The single-file half is AST rules (`ast-grep/rules/exceptions/`): no builtin raise,
 * no `HTTPException`, no stored instance. What a pattern cannot see is whether a
 * raised name is *defined in core* and whether it is *handled* — both need two
 * files at once, so they live here:
 *
 *   1. every `raise X(...)` in `backend/app/` names a class declared in
 *      `app/core/exceptions.py` (or the declared third-party allowlist)
 *   2. every core exception has exactly one handler in
 *      `setup_exception_handler`, and every handler maps a class that exists
 *   3. every handler returns the uniform error body (`detail`, `code`,
 *      `request_id`) so clients can branch on `code`, not on prose
 *   4. exception classes are named `*Error`
 *
 * Pure validation — no side effects.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");
const exceptionsModule = join(appDir, "core", "exceptions.py");

/**
 * Third-party exceptions the handler layer maps on purpose. Each entry states
 * why the class cannot be a core class: it is raised by a library, not by us.
 */
const EXTERNAL_HANDLED: Record<string, string> = {
  IntegrityError: "raised by the driver on a constraint violation; mapped to 409 rather than a 500",
  StaleDataError: "raised by SQLAlchemy's optimistic lock (version_id_col)",
};

/**
 * Names owned by `ast-grep/rules/exceptions/`. Reporting them here too would mean two
 * owners for one invariant — and the AST rules are the precise ones: they know a
 * `ValueError` inside a Pydantic validator is the framework's contract, which a
 * name scan cannot see.
 */
const AST_OWNED: Record<string, true> = {
  ValueError: true,
  RuntimeError: true,
  Exception: true,
  KeyError: true,
  TypeError: true,
  AssertionError: true,
  NotImplementedError: true,
  HTTPException: true,
};

const RAISE_CALL = /^\s*raise\s+([A-Z]\w*)\s*\(/gm;
const CLASS_DEF = /^class\s+(\w+)\s*\(([^)]*)\)\s*:/gm;
const HANDLER = /@app\.exception_handler\((\w+)\)/g;

/** One response shape for every failure: clients branch on `code`, not prose. */
const REQUIRED_BODY_KEYS = ["detail", "code", "REQUEST_ID_KEY"];

export function checkBackendExceptions(): string[] {
  const issues: string[] = [];
  if (!existsSync(exceptionsModule)) {
    return ["core/exceptions.py is missing — every raised exception is defined there"];
  }
  const source = readFileSync(exceptionsModule, "utf-8");
  const defined = new Set([...source.matchAll(CLASS_DEF)].map((match) => match[1]));

  issues.push(...checkNaming(defined));
  issues.push(...checkRaisedNames(defined));
  issues.push(...checkHandlers(source, defined));
  issues.push(...checkHandlerBodies(source));
  return issues;
}

/** A `*Error` suffix is what makes a raise site readable at a glance. */
function checkNaming(defined: Set<string>): string[] {
  const issues: string[] = [];
  for (const name of defined) {
    if (!name.endsWith("Error")) {
      issues.push(
        `core/exceptions.py: ${name} does not end in "Error" — the suffix is what marks a ` +
          "class as raisable at its use site",
      );
    }
  }
  return issues;
}

/** Every raised class is a core class: one vocabulary, one handler layer. */
function checkRaisedNames(defined: Set<string>): string[] {
  const issues: string[] = [];
  for (const path of walk(appDir)) {
    const source = readFileSync(path, "utf-8");
    const label = relative(path);
    for (const match of source.matchAll(RAISE_CALL)) {
      const name = match[1];
      if (AST_OWNED[name] === true) continue; // ast-grep/rules/exceptions/ owns these
      if (defined.has(name) || EXTERNAL_HANDLED[name] !== undefined) continue;
      const line = source.slice(0, match.index ?? 0).split("\n").length;
      issues.push(
        `${label}:${line}: raise ${name}() is not defined in app/core/exceptions.py — ` +
          "define it there with a handler, or raise an existing core exception",
      );
    }
  }
  return issues;
}

/** Class ↔ handler, both ways: an unhandled core exception answers 500. */
function checkHandlers(source: string, defined: Set<string>): string[] {
  const issues: string[] = [];
  const handled = [...source.matchAll(HANDLER)].map((match) => match[1]);
  const handledSet = new Set(handled);

  for (const name of defined) {
    if (handledSet.has(name)) continue;
    // A subclass may be answered by its parent's handler, but only if the parent
    // is handled — otherwise the whole branch is unmapped.
    const parents = parentsOf(source, name);
    if (parents.some((parent) => handledSet.has(parent))) continue;
    issues.push(
      `core/exceptions.py: ${name} has no @app.exception_handler — an unhandled exception ` +
        "escapes as 500 with a stack trace instead of the uniform error body",
    );
  }
  for (const name of handled) {
    if (defined.has(name) || EXTERNAL_HANDLED[name] !== undefined) continue;
    issues.push(
      `core/exceptions.py: handler registered for ${name}, which is not defined here — ` +
        "an intentional third-party mapping must be declared in the rule and the allowlist",
    );
  }
  for (const [name, count] of countBy(handled)) {
    if (count > 1) {
      issues.push(`core/exceptions.py: ${count} handlers registered for ${name} — the last wins`);
    }
  }
  return issues;
}

/** One response shape: clients branch on `code`, never on prose. */
function checkHandlerBodies(source: string): string[] {
  const issues: string[] = [];
  const blocks = source.split(/@app\.exception_handler\(/).slice(1);
  for (const block of blocks) {
    const name = /^(\w+)\)/.exec(block)?.[1] ?? "unknown";
    const body = block.split(/\n@app\.exception_handler\(/)[0];
    for (const key of REQUIRED_BODY_KEYS) {
      if (!body.includes(key)) {
        issues.push(
          `core/exceptions.py: ${name} handler response is missing ${key} — every error body ` +
            "carries detail, code and request_id",
        );
      }
    }
    if (!/status_code=\d{3}/.test(body)) {
      issues.push(`core/exceptions.py: ${name} handler declares no explicit status_code`);
    }
  }
  return issues;
}

// ============================================================
// Helpers
// ============================================================

function parentsOf(source: string, name: string): string[] {
  const match = new RegExp(`^class\\s+${name}\\s*\\(([^)]*)\\)`, "m").exec(source);
  return match === null ? [] : match[1].split(",").map((parent: string) => parent.trim());
}

function countBy(names: string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1);
  return counts;
}

/** Every .py file under app/, excluding caches. Validators are AST-scoped. */
function walk(dir: string): string[] {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return [];
  const found: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...walk(path));
      continue;
    }
    if (entry.name.endsWith(".py")) found.push(path);
  }
  return found;
}

function relative(path: string): string {
  return path.startsWith(projectRoot) ? path.slice(projectRoot.length + 1) : path;
}
