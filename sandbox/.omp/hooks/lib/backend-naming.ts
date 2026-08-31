// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * Domain naming checks — module-private functions, conftest registration
 * (backend-naming.md).
 *
 * Validates:
 *   - module-level functions never referenced by another module are `_`-prefixed
 *   - every CRUD model is imported in tests/conftest.py
 *
 * Pure validation — no ast-grep, no side effects. Called by the
 * check-backend-domain orchestrator.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

export function checkDomainNaming(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");

  issues.push(...checkModulePrivateFunctions(base));
  issues.push(...checkConftestModelImports(base));
  issues.push(...checkSectionDividers(base));

  return issues;
}

/**
 * Section divider standard (backend-naming.md "Section Dividers").
 *
 * Every module in backend/app/ is split into labeled sections by
 * `# ====...====` divider pairs. Validates:
 *   - every .py module (except __init__.py) has at least one divider pair
 *   - the first divider pair is `# Imports` and precedes any code
 *   - section names come from the canonical set
 *   - section order follows the canonical order (Imports → Constants →
 *     Classes → Functions → Dependencies → Router → …)
 */
function checkSectionDividers(base: string): string[] {
  const issues: string[] = [];
  const CANONICAL_ORDER = [
    "Imports",
    "Constants",
    "Classes",
    "Functions",
    "Dependencies",
    "Router",
    "Middleware",
    "Lifespan",
    "App Setup",
    "Router Registration",
  ];
  const pyFiles: string[] = listAppPython(base);
  const mainPy = join(base, "main.py");
  if (existsSync(mainPy)) pyFiles.push(mainPy);

  for (const path of pyFiles) {
    const fileName = path.split("/").pop() ?? "";
    const lines = readFileSync(path, "utf-8").split("\n");
    const names: string[] = [];
    for (let i = 0; i < lines.length; i++) {
      if (/^# ={60}$/.test(lines[i]) && i + 1 < lines.length) {
        const name = lines[i + 1].match(/^# ([A-Z][A-Za-z ]+)$/);
        if (name) names.push(name[1]);
      }
    }
    if (names.length === 0) {
      issues.push(
        `${fileName}: missing section dividers — every module needs ` +
          "`# ====...====` / `# <Section>` pairs (backend-naming.md)",
      );
      continue;
    }
    if (names[0] !== "Imports") {
      issues.push(`${fileName}: first section must be "Imports" (found "${names[0]}")`);
    }
    const firstCode = lines.findIndex(
      (l: string) => l && !l.startsWith("#") && !l.startsWith('"""') && !l.startsWith("'''"),
    );
    const firstDivider = lines.findIndex((l: string) => /^# ={60}$/.test(l));
    if (firstCode !== -1 && firstDivider > firstCode) {
      issues.push(`${fileName}: code appears before the first section divider`);
    }
    // Import order, grouping and the blank lines after the block are owned by
    // ruff's `I` rules (`lines-after-imports = 2`). This file used to *require*
    // `# isort: off` / `# isort: on` around the block, on the theory that isort
    // would otherwise absorb the divider comments — measured false: ruff leaves
    // a banner in place whether or not a blank line separates it. What is left
    // is the inverse claim: nothing may switch the sorter off locally, or the
    // order stops being a standard and becomes a per-file opinion.
    lines.forEach((line: string, index: number) => {
      if (/^\s*#\s*isort:\s*\S/.test(line) || /#\s*(?:ruff:\s*)?noqa:[^\n]*\bI0\d\d\b/.test(line)) {
        issues.push(
          `${fileName}:${index + 1}: import-order suppression (${line.trim()}) — ` +
            "ruff's I rules own the import block; there is no local exemption",
        );
      }
    });
    for (const name of names) {
      if (!CANONICAL_ORDER.includes(name)) {
        issues.push(`${fileName}: unknown section "${name}" — use one of ${CANONICAL_ORDER.join(", ")}`);
      }
    }
    const orderIndexes = names.map((n) => CANONICAL_ORDER.indexOf(n));
    for (let i = 1; i < orderIndexes.length; i++) {
      if (orderIndexes[i] <= orderIndexes[i - 1]) {
        issues.push(
          `${fileName}: section "${names[i]}" is out of order — canonical order is ` +
            CANONICAL_ORDER.join(" → "),
        );
        break;
      }
    }
  }
  return issues;
}

/**
 * Scans backend/app/ for module-level functions that are never referenced by
 * any other module. Such functions are module-private and must be prefixed
 * with `_` (e.g. `_lifespan`). Cross-file analysis — ast-grep cannot express
 * "referenced elsewhere", so this scans other modules' contents directly.
 *
 * A function is PUBLIC (no `_` required) when any other module:
 *   - imports it (`from app.x import NAME`, or `import app.x` + `app.x.NAME`)
 *   - references it via `Depends(NAME)` (DI factory)
 *   - or the function itself is registered via a decorator (`@router.`, `@app.`)
 *     — FastAPI routes are public endpoints without imports.
 */
function checkModulePrivateFunctions(base: string): string[] {
  const issues: string[] = [];
  const pyFiles: string[] = listAppPython(base);
  const mainPy = join(base, "main.py");
  if (existsSync(mainPy)) pyFiles.push(mainPy);

  // Collect all module contents for cross-module reference scanning.
  const allContents = new Map<string, string>(); // path → content
  for (const p of pyFiles) {
    allContents.set(p, readFileSync(p, "utf-8"));
  }

  for (const [path, content] of allContents) {
    const fileName = path.split("/").pop() ?? "";
    const moduleName = fileName.replace(/\.py$/, "");

    // Module-level function definitions (no indentation), with their decorators.
    // Decorator line: @router.post("/", status_code=...) — capture the whole line.
    const defs = [...content.matchAll(/^(?:(@\S[^\n]*)\s*\n)?(async\s+)?def\s+(\w+)\s*\(/gm)];
    for (const m of defs) {
      const decorator = m[1] ?? "";
      const name = m[3];
      if (name.startsWith("_") || name.startsWith("__")) continue; // already private or dunder
      if (decorator.startsWith("@router.") || decorator.startsWith("@app.")) continue; // FastAPI route

      // Public if ANY other module references it: import, module.name, Depends().
      // Also public if the SAME module wires it into DI (Depends(NAME)) — DI
      // factories are exported via Annotated aliases, not direct imports.
      // Imports may be single-line or parenthesized multi-line.
      let isPublic = false;
      const importRe = new RegExp(
        `\\bfrom\\s+[\\w.]+\\s+import\\s+(?:[^\\n(]+|\\()[^)]*\\b${name}\\b`,
      );
      for (const [otherPath, otherContent] of allContents) {
        if (otherPath === path) {
          if (new RegExp(`\\bDepends\\(\\s*${name}\\s*\\)`).test(otherContent)) { isPublic = true; break; }
          continue;
        }
        if (importRe.test(otherContent)) { isPublic = true; break; }
        if (new RegExp(`\\bimport\\s+[\\w.]*\\b${name}\\b`).test(otherContent)) { isPublic = true; break; }
        if (new RegExp(`\\b${moduleName}\\.${name}\\b`).test(otherContent)) { isPublic = true; break; }
        if (new RegExp(`\\bDepends\\(\\s*${name}\\s*\\)`).test(otherContent)) { isPublic = true; break; }
      }
      if (isPublic) continue;

      issues.push(
        `${fileName}: module-level function "${name}" is never referenced by ` +
          "another module — module-private functions must be prefixed with _ " +
          "(e.g. _lifespan)",
      );
    }
  }

  return issues;
}

/**
 * Every module under `backend/app/`, recursively, excluding `main.py` (callers
 * append it explicitly) and package markers.
 *
 * Walked, not listed. The eight-directory list this replaced missed two things
 * at once: a directory nobody had added to it, and - after the domain folders
 * landed - every file inside `models/integration/`, because it read one level
 * deep. Both were silent: the loop simply had fewer files to check.
 */
function listAppPython(base: string): string[] {
  const found: string[] = [];
  const walk = (directory: string): void => {
    if (!existsSync(directory)) return;
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "__pycache__") continue;
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        walk(path);
        continue;
      }
      if (!entry.name.endsWith(".py") || entry.name === "__init__.py") continue;
      if (directory === base && entry.name === "main.py") continue;
      found.push(path);
    }
  };
  walk(base);
  return found;
}

/**
 * Verifies that every CRUD model in app/models/ is imported in
 * tests/conftest.py. Without the import, Base.metadata.create_all() skips the
 * model's table in the in-memory SQLite test DB — tests then fail with
 * "no such table". Mirrors the alembic/env.py registration rule.
 */
function checkConftestModelImports(base: string): string[] {
  const issues: string[] = [];
  const modelDir = join(base, "models");
  // tests/ moved out of app/ — conftest lives at backend/tests/conftest.py.
  const conftestPath = join(projectRoot, "backend", "tests", "conftest.py");
  if (!existsSync(modelDir) || !existsSync(conftestPath)) return issues;

  const conftestContent = readFileSync(conftestPath, "utf-8");
  for (const f of readdirSync(modelDir)) {
    if (!f.endsWith(".py") || f === "__init__.py" || f === "base.py") continue;
    const name = f.replace(/\.py$/, "");
    if (!new RegExp(`from app\\.models\\.${name} import(?:\\s+\\w+|\\s*\\()`).test(conftestContent)) {
      issues.push(
        `conftest.py: model "${name}" not imported — Base.metadata.create_all() ` +
          "skips its table in the test DB; add `from app.models.<name> import <Name>`",
      );
    }
  }
  return issues;
}
