/**
 * A hook must measure the domains it governs, never name them.
 *
 * Measured three times in one session: `check-backend-tests.ts` carried
 * `new Set(["integration"])`, `check-backend-transaction.ts` filtered
 * `file !== "integration.py"`, and `lib/backend-domain-structure.ts` skipped
 * `name === "integration"`. All three asked *"is this domain literally named
 * integration"* instead of *"does this domain own more than one model file"*,
 * so all three silently stopped matching the day `integration.py` became five
 * files. `check-frontend-api-layer.ts` carried the same shape as a regex —
 * `/(?:auth|user|batch|integration)/` — which had already been missing
 * `/health` for as long as it existed.
 *
 * None of those failures was loud. A name-based classifier does not error when
 * the name stops applying; it simply matches nothing and reports success. That
 * is what makes this worth a gate rather than a review habit.
 *
 * ## What is flagged
 *
 * A discoverable domain name written as a literal in a **classification**
 * position — equality, a membership call, a collection literal, or a regex
 * alternation. Those are the positions that decide *which* domains a check
 * applies to.
 *
 * A literal used to **address** one known file (`join(routersDir, "auth.py")`)
 * is not this defect: it names a file the hook is about, it does not classify a
 * discovered set, and it fails loudly when the file moves.
 *
 * ## The two escapes
 *
 * 1. **A dedicated hook may name its domain.** `lib/backend-integration-*.ts`
 *    exists to check `integration`; requiring it to measure that would be
 *    circular. Membership is read from the hook's own filename, so it needs no
 *    list.
 * 2. **An inline `// domain-literal:` annotation with a reason.** Some
 *    collisions are real: `hook-publish-consent.ts` compares a *message role*
 *    named `user`, which is not the `user` domain at all. Writing the reason
 *    down is the whole point — and a stale annotation fails, so exemptions
 *    cannot pile up unread.
 *
 * ## Falsified
 *
 * Planted in a hook file, run, restored - all six fired, and the tree measured
 * clean again afterwards:
 *
 * | Planted | Detected as |
 * |---|---|
 * | `new Set(["integration"])` | collection |
 * | `file !== "integration.py"` | equality |
 * | `name === "integration"` | equality |
 * | `/(?:auth\|user\|batch\|integration)/` | regex alternation (all three names) |
 * | `["integration_secret"].includes(x)` | collection, one table of an aggregate |
 * | a bare `// domain-literal:` with no sentence | unreasoned annotation |
 *
 * Two shapes are deliberately silent, and were checked: `join(dir, "auth.py")`
 * (addressing, not classifying) and this file's own prose, which names every
 * defect above.
 */

// @ts-expect-error - Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error - Node builtin, not project-compiled
import { join } from "node:path";
import { resolveProjectRoot } from "./hook-project-root.ts";

const projectRoot = resolveProjectRoot();
const hooksDir = join(projectRoot, ".omp", "hooks");

/** The directories whose `.ts` files are hooks or the libs hooks delegate to. */
const HOOK_DIRECTORIES = ["post", "lib", "pre"];

/** `// domain-literal: <reason>` - the annotated escape, reason required. */
const ANNOTATION = /\/\/\s*domain-literal:\s*(.*)$/;

/**
 * A marker with no sentence after it is not a reason. Long enough to force a
 * clause, short enough that an honest one-liner passes.
 */
const MIN_REASON_LENGTH = 20;

/** A model/repository/router file stem that names no table of its own. */
const NOT_A_DOMAIN = new Set(["base", "__init__", "health"]);

export function checkHookDomainLiterals(): string[] {
  const issues: string[] = [];
  const domains = discoverDomains();
  if (domains.size === 0) return issues;
  const entities = discoverEntities(domains);
  if (entities.length === 0) return issues;
  const patterns = classificationPatterns(entities);

  for (const relative of listHookFiles()) {
    const source = readFileSync(join(hooksDir, relative), "utf-8");
    const fileName = relative.split("/").pop() ?? "";
    const scanned = scanLines(source);

    scanned.forEach((line: ScannedLine, index: number) => {
      const named = classifiedNames(line.code, entities, patterns);
      const annotation = ANNOTATION.exec(line.comment);

      if (named.length === 0) {
        // A stale annotation is worse than none: it documents a rule the code
        // no longer breaks, and the next reader trusts it.
        if (annotation !== null && !annotates(scanned[index + 1]?.code ?? "", entities, patterns)) {
          issues.push(
            `${relative}:${index + 1}: stale \`// domain-literal:\` annotation - ` +
              "no domain name is classified on this line or the next; delete it",
          );
        }
        return;
      }

      const unowned = named.filter((name) => !fileName.includes(owningDomain(name, domains) ?? name));
      if (unowned.length === 0) return;

      const reason = (annotation?.[1] ?? annotationAbove(scanned, index)).trim();
      if (reason.length >= MIN_REASON_LENGTH) return;
      if (reason.length > 0) {
        issues.push(
          `${relative}:${index + 1}: \`// domain-literal:\` needs a reason, not a marker - ` +
            `say why '${unowned.join(", ")}' is right here`,
        );
        return;
      }
      issues.push(
        `${relative}:${index + 1}: classifies domains by name ('${unowned.join(", ")}') - ` +
          "discover them instead (services/*.py, routers/*.py, or the frontend service files), " +
          "or state the reason inline with `// domain-literal: <why this name is right>`",
      );
    });
  }

  return issues;
}

/** Every hook and hook-lib file, so a lib cannot hide what a hook may not do. */
function listHookFiles(): string[] {
  const files: string[] = [];
  for (const directory of HOOK_DIRECTORIES) {
    const path = join(hooksDir, directory);
    if (!existsSync(path)) continue;
    for (const file of readdirSync(path)) {
      if (file.endsWith(".ts") && !file.endsWith(".d.ts")) files.push(`${directory}/${file}`);
    }
  }
  return files;
}

/**
 * A domain is a service file - the same source `check-backend-domain` and
 * `check-frontend-domain` discover from, so this gate and the checks it
 * governs cannot disagree about what a domain is.
 */
function discoverDomains(): Set<string> {
  const domains = new Set<string>();
  const backendServices = join(projectRoot, "backend", "app", "services");
  if (existsSync(backendServices)) {
    for (const entry of readdirSync(backendServices, { withFileTypes: true })) {
      if (entry.name.startsWith("__")) continue;
      // A domain whose service has grown into several files is a folder here,
      // exactly as in the other layers.
      if (entry.isDirectory()) domains.add(entry.name);
      else if (entry.name.endsWith(".py")) domains.add(entry.name.slice(0, -3));
    }
  }
  const frontendServices = join(projectRoot, "frontend", "src", "lib", "api", "services");
  if (existsSync(frontendServices)) {
    for (const file of readdirSync(frontendServices)) {
      if (file.endsWith(".service.ts")) domains.add(file.slice(0, -".service.ts".length));
    }
  }
  for (const name of NOT_A_DOMAIN) domains.delete(name);
  return domains;
}

/**
 * The domains plus the per-table names they own (`integration_provider`), so
 * naming one table of an aggregate is caught the same as naming the aggregate.
 *
 * Reads `<layer>/<domain>/<table>.py` as well as the flat `<domain>_<table>.py`.
 * Measured: while this read only the flat form, moving the five integration
 * files into `models/integration/` silently dropped every per-table name from
 * the gate - `["integration_secret"].includes(x)` planted in an unrelated hook
 * went undetected, which is the exact failure mode this module exists to stop.
 */
function discoverEntities(domains: Set<string>): string[] {
  const entities = new Set<string>(domains);
  for (const directory of ["models", "routers", "repositories", "schemas", "services"]) {
    const path = join(projectRoot, "backend", "app", directory);
    if (!existsSync(path)) continue;
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      if (entry.name.startsWith("__")) continue;
      if (entry.isDirectory()) {
        // The folder is the domain; each file inside is `<domain>_<file>`.
        if (!domains.has(entry.name)) continue;
        for (const inner of readdirSync(join(path, entry.name))) {
          if (!inner.endsWith(".py") || inner.startsWith("__")) continue;
          entities.add(`${entry.name}_${inner.slice(0, -3)}`);
        }
        continue;
      }
      if (!entry.name.endsWith(".py")) continue;
      const stem = entry.name.slice(0, -3);
      if (NOT_A_DOMAIN.has(stem)) continue;
      if (owningDomain(stem, domains) !== null) entities.add(stem);
    }
  }
  return [...entities];
}

/** `integration_provider` belongs to `integration`; `user` belongs to itself. */
function owningDomain(name: string, domains: Set<string>): string | null {
  if (domains.has(name)) return name;
  for (const domain of domains) {
    if (name.startsWith(`${domain}_`)) return domain;
  }
  return null;
}

/**
 * The four positions that decide *which* domains a check applies to. A path
 * argument is deliberately absent: `join(dir, "auth.py")` addresses one file.
 */
function classificationPatterns(entities: string[]): RegExp[] {
  const alternation = entities.join("|");
  const literal = `["'\`](?:${alternation})(?:\\.py|\\.ts)?["'\`]`;
  return [
    new RegExp(`[!=]==\\s*${literal}`),
    new RegExp(`\\.(?:has|includes|startsWith|endsWith)\\(\\s*${literal}`),
    new RegExp(`(?:new Set\\(\\[|=\\s*\\[)[^\\]]*${literal}`),
    new RegExp(`\\((?:\\?:)?(?:${alternation})\\|`),
  ];
}

/** The entity names a single line classifies, if it classifies any. */
function classifiedNames(line: string, entities: string[], patterns: RegExp[]): string[] {
  if (!patterns.some((pattern) => pattern.test(line))) return [];
  return entities.filter((name) =>
    new RegExp(`["'\`]${name}(?:\\.py|\\.ts)?["'\`]|\\b${name}\\|`).test(line),
  );
}

function annotates(nextLine: string, entities: string[], patterns: RegExp[]): boolean {
  return classifiedNames(nextLine, entities, patterns).length > 0;
}

/** The annotation may sit above the line when the line is already long. */
function annotationAbove(scanned: ScannedLine[], index: number): string {
  return ANNOTATION.exec(scanned[index - 1]?.comment ?? "")?.[1] ?? "";
}

/** One source line, split into the code it runs and the line comment it carries. */
interface ScannedLine {
  /** Executable text, with comment regions blanked to keep column offsets. */
  code: string;
  /** The trailing `//` comment, or `""` - the only place an annotation counts. */
  comment: string;
}

/**
 * Splits code from comments the way the compiler would, because the cheap
 * version was wrong here in both directions: every docstring in this harness
 * narrates by name the very defects it prevents (read as code, the
 * explanations flag themselves), and this module's own warning text quotes
 * `// domain-literal:` inside a template literal (read as a comment, the
 * message is an annotation). Strings and block comments must be tracked to
 * tell those apart, so they are.
 *
 * Comment regions are blanked rather than dropped: reported line and column
 * numbers stay the file's own.
 */
function scanLines(source: string): ScannedLine[] {
  const lines: ScannedLine[] = [];
  let inBlock = false;

  for (const raw of source.split("\n")) {
    // Quote state is per line on purpose. A regex literal carries quote
    // characters (`\("([^"]*)"` holds three), and this scanner does not parse
    // regex literals - carrying the state across lines let one such line hold
    // a string open to end of file, which swallowed every block comment after
    // it. Measured: it read this module's own explanatory docstrings as code.
    // Per line, an unparsable line costs that line and nothing else.
    let quote: string | null = null;
    let code = "";
    let comment = "";
    let index = 0;

    while (index < raw.length) {
      const pair = raw.slice(index, index + 2);
      if (inBlock) {
        if (pair === "*/") inBlock = false;
        code += pair === "*/" ? "  " : " ";
        index += pair === "*/" ? 2 : 1;
        continue;
      }
      if (quote !== null) {
        if (raw[index] === "\\") {
          code += raw.slice(index, index + 2);
          index += 2;
          continue;
        }
        if (raw[index] === quote) quote = null;
        code += raw[index];
        index += 1;
        continue;
      }
      if (pair === "/*") {
        inBlock = true;
        code += "  ";
        index += 2;
        continue;
      }
      if (pair === "//") {
        comment = raw.slice(index);
        break;
      }
      if (raw[index] === '"' || raw[index] === "'" || raw[index] === "`") quote = raw[index];
      code += raw[index];
      index += 1;
    }

    lines.push({ code, comment });
  }

  return lines;
}
