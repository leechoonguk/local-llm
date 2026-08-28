import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

/**
 * Check-Environment Post Hook
 *
 * After tool execution, validates the environment contract in
 * .omp/rules/environment.md:
 *   1. backend/.env (or .env.example) defines the required variables:
 *      ENV, DATABASE_URL, ADMIN_EMAIL, ITEMS_PER_USER, APP_NAME
 *   2. settings.py declares the matching fields
 *   3. Root ↔ backend shared variable sync: APP_NAME/ADMIN_EMAIL/ITEMS_PER_USER
 *      must match between root .env (docker-compose) and backend/.env
 *   4. AST rules (.omp/ast-grep/rules/environment/): no os.environ/os.getenv direct
 *      use, no hardcoded connection strings or service ports in backend code
 *
 * Note: the root .env.example also carries APP_NAME/ADMIN_EMAIL/ITEMS_PER_USER
 * — those are consumed by docker-compose.yml (backend service environment),
 * not by the backend app itself. The backend app reads backend/.env.
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
const cwd = process.cwd();
// Adjust cwd to project root if running from backend/
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


/** Required variables per environment.md. */
const REQUIRED_VARS = ["ENV", "DATABASE_URL", "ADMIN_EMAIL", "ITEMS_PER_USER", "APP_NAME"];

/**
 * Variables shared between the root .env (docker-compose) and backend/.env.
 * docker-compose.yml passes these from the root .env into the backend
 * container, so a value mismatch means Docker and local runs diverge.
 */
const SHARED_VARS = ["APP_NAME", "ADMIN_EMAIL", "ITEMS_PER_USER"];

/**
 * Keys whose value is a credential: the committed reference carries a
 * placeholder on purpose, so its value must **not** be required to match the
 * real file. Matched by name, not by a list, so a new credential is covered the
 * day it is added.
 */
const CREDENTIAL_KEY = /SECRET|PASSWORD|TOKEN/;

export default function checkBackendEnvironment(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-environment", event, () => {
    // Skip read-only tools — they cannot change env files.
    // hook-scope: global — 환경/설정 드리프트는 경로로 좁히면 놓친다
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendEnvironmentSync();
    if (issues.length === 0) {
      resetSuppression("check-environment"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-environment",
      issues,
      "run make check-environment for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-environment") };
  }));
}

function checkBackendEnvironmentSync(): string[] {
  const issues: string[] = [];
  const backendDir = join(projectRoot, "backend");

  // --- 0. AST rule validation (ast-grep) ---
  // Structural checks for hardcoded env access that string matching cannot
  // express precisely:
  //   env-os-environ-direct.yml     — os.environ/os.getenv direct use forbidden
  //   env-hardcoded-connection.yml   — literal postgresql+asyncpg:// strings
  //   env-hardcoded-port.yml        — literal localhost service ports
  const astRulesDir = join(projectRoot, ".omp", "ast-grep", "rules", "environment");
  if (existsSync(astRulesDir)) {
    issues.push(...runAstRules(astRulesDir, [join(backendDir, "app")]));
  }

  // `settings.env` says where the code runs, never who may do what. Security
  // paths and migrations must decide from an explicit setting instead.
  const securityRules = join(projectRoot, ".omp", "ast-grep", "rules", "env-security");
  const securityPaths = [
    join(backendDir, "app", "core", "security.py"),
    join(backendDir, "app", "dependencies", "auth.py"),
    join(backendDir, "app", "routers", "auth.py"),
    join(backendDir, "alembic", "versions"),
  ].filter((path) => existsSync(path));
  if (existsSync(securityRules) && securityPaths.length > 0) {
    issues.push(...runAstRules(securityRules, securityPaths));
  }

  // --- 1. .env / .env.example required variables ---

  const envPath = join(backendDir, ".env");
  const envExamplePath = join(backendDir, ".env.example");
  const envContent = existsSync(envPath) ? readFileSync(envPath, "utf-8") : "";
  const envExampleContent = existsSync(envExamplePath) ? readFileSync(envExamplePath, "utf-8") : "";

  if (!existsSync(envPath) && !existsSync(envExamplePath)) {
    issues.push("backend/.env and backend/.env.example both missing");
  } else {
    const combined = `${envContent}\n${envExampleContent}`;
    for (const varName of REQUIRED_VARS) {
      if (!new RegExp(`^\\s*${varName}\\s*=`, "m").test(combined)) {
        issues.push(`missing required variable ${varName} in backend/.env (or .env.example)`);
      }
    }
  }

  // --- 2. Section comments + alignment (root .env style) ---
  // Both backend/.env and backend/.env.example must carry the root-style
  // section banner: a `# ===` header block plus `# --- <Section> ---`
  // markers grouping the variables, and every assignment must use the
  // aligned `KEY = value` form (space on both sides of `=`).
  for (const [label, content] of [
    ["backend/.env", envContent],
    ["backend/.env.example", envExampleContent],
  ] as const) {
    if (!content) continue;
    const hasBanner = /# ={3,}/.test(content);
    const hasSections = (content.match(/^# --- .+ ---$/gm) ?? []).length >= 2;
    if (!hasBanner) {
      issues.push(`${label} missing the "# ===..." header banner (root .env style)`);
    }
    if (!hasSections) {
      issues.push(`${label} missing "# --- <Section> ---" markers (need at least 2 sections, root .env style)`);
    }
    // Alignment: `KEY = value` — reject `KEY=value`, `KEY =value`, `KEY= value`.
    for (const m of content.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/gm)) {
      if (!/^\s*[A-Za-z_][A-Za-z0-9_]*\s=\s/m.test(m[0])) {
        issues.push(`${label}: '${m[1]}' must use aligned 'KEY = value' form (space on both sides of =)`);
      }
    }
  }

  // --- 3. settings.py declares the matching fields ---

  const settingsPath = join(backendDir, "app", "core", "settings.py");
  if (!existsSync(settingsPath)) {
    issues.push("backend/app/core/settings.py not found");
    return issues;
  }
  const settingsContent = readFileSync(settingsPath, "utf-8");
  for (const varName of REQUIRED_VARS) {
    const field = varName.toLowerCase();
    if (!new RegExp(`\\b${field}\\s*:`).test(settingsContent)) {
      issues.push(`settings.py missing field "${field}" for required variable ${varName}`);
    }
  }

  // --- 3. Root ↔ backend shared variable sync ---
  // docker-compose.yml passes APP_NAME/ADMIN_EMAIL/ITEMS_PER_USER from the
  // root .env into the backend container. If the values differ from
  // backend/.env, Docker and local runs diverge silently.
  const rootEnvPath = join(projectRoot, ".env");
  const rootEnvExamplePath = join(projectRoot, ".env.example");
  const rootEnvContent = existsSync(rootEnvPath) ? readFileSync(rootEnvPath, "utf-8") : "";
  const rootEnvExampleContent = existsSync(rootEnvExamplePath) ? readFileSync(rootEnvExamplePath, "utf-8") : "";

  for (const varName of SHARED_VARS) {
    const rootVal = extractEnvValue(rootEnvContent, varName) ?? extractEnvValue(rootEnvExampleContent, varName);
    const backendVal = extractEnvValue(envContent, varName) ?? extractEnvValue(envExampleContent, varName);
    if (rootVal === null || backendVal === null) continue; // missing side handled by checks 1/3
    if (rootVal !== backendVal) {
      issues.push(
        `${varName} mismatch: root .env=${rootVal} vs backend/.env=${backendVal} — ` +
          "docker-compose passes the root value into the container; keep them in sync",
      );
    }
  }

  // Root ↔ backend common-key comment parity: the `ENV` value is intentionally
  // divergent (container vs local), but every key that appears in both files
  // must carry the same preceding comment so the intent is documented once.
  if (rootEnvContent && envContent) {
    const rootComments = new Map(extractEnvEntries(rootEnvContent).map((e) => [e.key, e.comment]));
    const backendComments = new Map(extractEnvEntries(envContent).map((e) => [e.key, e.comment]));
    for (const key of rootComments.keys()) {
      if (!backendComments.has(key)) continue;
      if (rootComments.get(key) !== backendComments.get(key)) {
        issues.push(
          `root .env and backend/.env comment for ${key} differs` +
            `: root="${rootComments.get(key) ?? "(none)"}" vs backend="${backendComments.get(key) ?? "(none)"}"` +
            " — keep the same comment line above each common variable",
        );
      }
    }
  }

  // Root ⊇ backend key invariant: every key in backend/.env must exist in root
  // .env. docker-compose passes root values into the container; a backend-only
  // key means the container silently runs on a settings.py default instead of the
  // configured value — local and Docker diverge. Root-only keys (infra vars like
  // POSTGRES_*, backend defaults like CORS_ORIGINS) are expected and not flagged.
  if (rootEnvContent && envContent) {
    const rootKeys = new Set(extractEnvKeys(rootEnvContent));
    for (const key of extractEnvKeys(envContent)) {
      if (!rootKeys.has(key)) {
        issues.push(
          `backend/.env key ${key} is absent from root .env — docker-compose cannot pass it to the container; add it to root .env/.env.example and wire it through docker-compose.yml`,
        );
      }
    }
  }

  // --- 4. .env ↔ .env.example pair sync (root + backend) ---
  // The rule (environment.md) requires the same keys and the same `# --- <Section> ---`
  // markers across `.env` and `.env.example` for every pair. A missing key in the
  // real file breaks runtime; a key absent from the example drifts the committed
  // reference. Drift is checked bidirectionally so neither side rots silently.
  issues.push(...checkEnvPairSync(rootEnvPath, rootEnvExamplePath, "root .env", "root .env.example"));
  issues.push(...checkEnvPairSync(envPath, envExamplePath, "backend/.env", "backend/.env.example"));

  // --- 5. docker-compose.yml env indirection ---
  // Every backend-service environment value must be a `${VAR}` reference
  // resolved from the root .env — literal values in docker-compose.yml are
  // hardcoded configuration (except the phoenix SQL URL, which composes
  // POSTGRES_* fragments). The root .env (or .env.example) must define every
  // referenced variable.
  const composePath = join(projectRoot, "docker-compose.yml");
  if (existsSync(composePath)) {
    const compose = readFileSync(composePath, "utf-8");
    const rootEnvAll = `${rootEnvContent}\n${rootEnvExampleContent}`;
    // Find the backend service's environment block, then check each entry.
    const backendEnvMatch = compose.match(/backend:\n(?:\s+.*\n)*?\s+environment:\n((?:\s+[A-Z_]+:.*\n)+)/);
    const block = backendEnvMatch ? backendEnvMatch[1] : "";
    for (const m of block.matchAll(/^\s*([A-Z_]+):\s*(.+)$/gm)) {
      const [, varName, rawValue] = m;
      const value = rawValue.trim();
      const ref = value.match(/^\$\{([^}]+)\}$/);
      if (!ref) {
        // Allow the phoenix-style compose: `postgresql://${A}:${B}@...`
        // only when it references POSTGRES_* variables that exist.
        const inlineRefs = [...value.matchAll(/\$\{([^}]+)\}/g)].map((x) => x[1]);
        const allDefined = inlineRefs.length > 0 && inlineRefs.every((r) => new RegExp(`^\\s*${r}\\s*=`, "m").test(rootEnvAll));
        if (!allDefined) {
          issues.push(
            `docker-compose.yml: ${varName} is hardcoded ("${value}") — use \${VAR} resolved from root .env`,
          );
        }
        continue;
      }
      // The referenced variable must exist in root .env / .env.example.
      if (!new RegExp(`^\\s*${ref[1]}\\s*=`, "m").test(rootEnvAll)) {
        issues.push(
          `docker-compose.yml: ${varName} references \${${ref[1]}} but it is not defined in root .env (or .env.example)`,
        );
      }
    }
  }

  // --- 6. Shared variable order + comments sync ---
  // APP_NAME/ADMIN_EMAIL/ITEMS_PER_USER (plus ENV/DATABASE_URL which exist
  // in both files) must appear in the same relative order and carry the
  // same comment line in root .env and backend/.env. A reorder or a
  // comment drift between the two files makes them hard to diff.
  const sharedOrder = ["ENV", "DATABASE_URL", "APP_NAME", "ADMIN_EMAIL", "ITEMS_PER_USER"];
  const rootEntries = extractEnvEntries(rootEnvContent).filter((e) => sharedOrder.includes(e.key));
  const backendEntries = extractEnvEntries(envContent).filter((e) => sharedOrder.includes(e.key));
  const minLen = Math.min(rootEntries.length, backendEntries.length);
  for (let i = 0; i < minLen; i++) {
    const r = rootEntries[i];
    const b = backendEntries[i];
    if (r.key !== b.key) {
      issues.push(
        `shared var order mismatch at position ${i + 1}: root has ${r.key}, backend has ${b.key} — ` +
          "keep shared variables in the same order (ENV, DATABASE_URL, APP_NAME, ADMIN_EMAIL, ITEMS_PER_USER)",
      );
      break;
    }
    if (r.comment !== b.comment) {
      issues.push(
        `shared var '${r.key}' comment mismatch: root="${r.comment}" vs backend="${b.comment}" — use identical comments`,
      );
    }
  }

  return issues;
}

/** Parses `KEY = value` lines with their preceding comment (`# ...`). */
function extractEnvEntries(content: string): Array<{ key: string; comment: string; value: string }> {
  const entries: Array<{ key: string; comment: string; value: string }> = [];
  let pendingComment = "";
  for (const line of content.split(/\r?\n/)) {
    const comment = line.match(/^\s*#\s+(.+)$/);
    if (comment && !/^#{3,}/.test(line.trim()) && !/^# --- /.test(line.trim())) {
      pendingComment = comment[1].trim();
      continue;
    }
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (m) {
      entries.push({ key: m[1], comment: pendingComment, value: m[2].trim() });
      pendingComment = "";
    }
  }
  return entries;
}
/** Extracts the value of `VAR=...` from env file content, or null when absent. */
function extractEnvValue(content: string, varName: string): string | null {
  const m = content.match(new RegExp(`^\\s*${varName}\\s*=\\s*(.+)$`, "m"));
  return m ? m[1].trim() : null;
}

/** Extracts all variable names (`VAR=...`) from env file content. */
function extractEnvKeys(content: string): string[] {
  const keys: string[] = [];
  for (const line of content.split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (m) keys.push(m[1]);
  }
  return keys;
}

/**
 * Checks that an `.env`/`.env.example` pair exposes the same keys, the same
 * `# --- <Section> ---` markers, and the same per-variable preceding comment.
 * Skipped when either side is missing. Both directions are checked: a
 * key/section/comment present on one side but not the other is flagged so
 * neither the runtime file nor the committed reference rots silently.
 */
function checkEnvPairSync(
  envPath: string,
  examplePath: string,
  envLabel: string,
  exampleLabel: string,
): string[] {
  const issues: string[] = [];
  if (!existsSync(envPath) || !existsSync(examplePath)) return issues;
  const envContent = readFileSync(envPath, "utf-8");
  const exampleContent = readFileSync(examplePath, "utf-8");
  const envKeys = new Set(extractEnvKeys(envContent));
  const exampleKeys = new Set(extractEnvKeys(exampleContent));
  for (const key of exampleKeys) {
    if (!envKeys.has(key)) {
      issues.push(`${envLabel} missing key ${key} — present in ${exampleLabel}`);
    }
  }
  for (const key of envKeys) {
    if (!exampleKeys.has(key)) {
      issues.push(`${exampleLabel} missing key ${key} — present in ${envLabel} (reference file out of date)`);
    }
  }
  const sectionRe = /^# --- (.+) ---$/gm;
  const envSections = [...envContent.matchAll(sectionRe)].map((m) => m[1]);
  const exampleSections = [...exampleContent.matchAll(sectionRe)].map((m) => m[1]);
  const maxSections = Math.max(envSections.length, exampleSections.length);
  for (let i = 0; i < maxSections; i++) {
    if (envSections[i] !== exampleSections[i]) {
      issues.push(
        `${envLabel} and ${exampleLabel} section markers differ at position ${i + 1}` +
          `: ${envLabel}="${envSections[i] ?? "(none)"}" vs ${exampleLabel}="${exampleSections[i] ?? "(none)"}"` +
          " — keep the same # --- <Section> --- markers in the same order",
      );
      break;
    }
  }
  // Per-variable preceding comment parity — a comment drift between the real
  // file and the reference makes the pair hard to diff and hides intent.
  const envComments = new Map(extractEnvEntries(envContent).map((e) => [e.key, e.comment]));
  const exampleComments = new Map(extractEnvEntries(exampleContent).map((e) => [e.key, e.comment]));
  for (const key of new Set([...envComments.keys(), ...exampleComments.keys()])) {
    if (envComments.get(key) !== exampleComments.get(key)) {
      issues.push(
        `${envLabel} and ${exampleLabel} comment for ${key} differs` +
          `: ${envLabel}="${envComments.get(key) ?? "(none)"}" vs ${exampleLabel}="${exampleComments.get(key) ?? "(none)"}"` +
          " — keep the same comment line above each shared variable",
      );
    }
  }
  // Value parity — the reference is a copy of the real file, not a variant of
  // it. Measured gap this closes: `ALLOWED_HOSTS` gained a host in
  // `backend/.env` while `.env.example` kept the old list, and every other
  // check passed because keys, sections and comments were untouched. When an
  // environment genuinely needs different values, it gets its own file
  // (`.env.local` / `.env.dev`), not a silent divergence inside one pair.
  const envValues = new Map(extractEnvEntries(envContent).map((e) => [e.key, e.value]));
  const exampleValues = new Map(extractEnvEntries(exampleContent).map((e) => [e.key, e.value]));
  for (const [key, value] of envValues) {
    if (CREDENTIAL_KEY.test(key)) continue;
    const reference = exampleValues.get(key);
    if (reference === undefined || reference === value) continue;
    issues.push(
      `${envLabel} and ${exampleLabel} value for ${key} differs: "${value}" vs "${reference}" — ` +
        "the pair must carry the same value (credentials excepted); split environments into " +
        "their own env file instead of diverging one pair",
    );
  }
  return issues;
}

// Direct execution (make check-environment): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-environment.ts")) {
  const issues = checkBackendEnvironmentSync();
  console.log("==> check-environment");
  if (issues.length === 0) {
    console.log("    PASS: backend environment contract valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-environment");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
