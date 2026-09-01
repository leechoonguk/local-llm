/**
 * Check-Decks-Sync Post Hook
 *
 * After tool execution, verifies that the harness documentation deck
 * (decks/harness-rules/slides.md) mentions every harness artifact:
 *   - rule files in .omp/rules/ (filenames minus .md)
 *   - pre hooks in .omp/hooks/pre/ (filenames minus .ts)
 *   - post hooks in .omp/hooks/post/ (filenames minus .ts)
 *   - AST rule dirs in .omp/ast-grep/rules/ (directory names)
 *
 * A mention is a substring match of the artifact name in the deck source.
 * The check is additive — it only flags artifacts missing from the deck,
 * never extra content. Per decks-sync.md, the deck must be updated in the
 * same change that modifies the harness.
 *
 * This is a read-only check — it does NOT block tool calls.
 * To add/remove artifacts: update .omp/* and decks/harness-rules/slides.md,
 * then run `make check-decks-sync` (part of `make verify`) to validate.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { createHash } from "node:crypto";
import { touchesStrict } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, ".omp")) ? cwd : join(cwd, "..");
const ompDir = join(projectRoot, ".omp");
const deckPath = join(projectRoot, "decks", "harness-rules", "slides.md");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkDecksSync(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-decks-sync", event, () => {
    // Skip read-only tools — they cannot change .omp/ or decks/ files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesStrict(event, [".omp/", "decks/"])) return;

    const issues = checkDecksSyncSync();
    if (issues.length === 0) {
      resetSuppression("check-decks-sync"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-decks-sync",
      issues,
      "run make check-decks-sync for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-decks-sync") };
  }));
}

function checkDecksSyncSync(): string[] {
  const issues: string[] = [];

  if (!existsSync(deckPath)) {
    issues.push(`deck file not found: decks/harness-rules/slides.md`);
    return issues;
  }
  const deckContent = readFileSync(deckPath, "utf-8");

  // Rule files: .omp/rules/*.md → names minus .md
  const rulesDir = join(ompDir, "rules");
  if (existsSync(rulesDir)) {
    for (const file of readdirSync(rulesDir)) {
      if (!file.endsWith(".md")) continue;
      const name = file.replace(/\.md$/, "");
      if (!deckContent.includes(name)) {
        issues.push(`rule '${name}' not mentioned in decks/harness-rules/slides.md`);
      }
    }
  }

  // Pre hooks: .omp/hooks/pre/*.ts → names minus .ts
  const preDir = join(ompDir, "hooks", "pre");
  if (existsSync(preDir)) {
    for (const file of readdirSync(preDir)) {
      if (!file.endsWith(".ts")) continue;
      const name = file.replace(/\.ts$/, "");
      if (!deckContent.includes(name)) {
        issues.push(`pre hook '${name}' not mentioned in decks/harness-rules/slides.md`);
      }
    }
  }

  // Post hooks: .omp/hooks/post/*.ts → names minus .ts
  const postDir = join(ompDir, "hooks", "post");
  if (existsSync(postDir)) {
    for (const file of readdirSync(postDir)) {
      if (!file.endsWith(".ts")) continue;
      const name = file.replace(/\.ts$/, "");
      if (!deckContent.includes(name)) {
        issues.push(`post hook '${name}' not mentioned in decks/harness-rules/slides.md`);
      }
    }
  }

  // Extensions: .omp/extensions/*/ → directory names (auto-loaded session behaviour)
  const extensionsRoot = join(ompDir, "extensions");
  if (existsSync(extensionsRoot)) {
    for (const dir of readdirSync(extensionsRoot, { withFileTypes: true })) {
      if (!dir.isDirectory()) continue;
      if (!deckContent.includes(dir.name)) {
        issues.push(`extension '${dir.name}' not mentioned in decks/harness-rules/slides.md`);
      }
    }
  }

  // AST rule dirs: .omp/ast-grep/rules/*/ → directory names
  const astRulesDir = join(ompDir, "ast-grep", "rules");
  if (existsSync(astRulesDir)) {
    for (const dir of readdirSync(astRulesDir, { withFileTypes: true })) {
      if (!dir.isDirectory()) continue;
      if (!deckContent.includes(dir.name)) {
        issues.push(`AST rule dir '${dir.name}' not mentioned in decks/harness-rules/slides.md`);
      }
    }
  }

  // Content-hash check: every artifact hash recorded in the deck (via
  // `<!-- sync: <name>=<hash> -->` comments written by decks/scripts/sync-hashes.mjs)
  // must match the live file. A mismatch means the harness changed but the
  // deck was not refreshed — run `make build` in decks/ to resync.
  issues.push(...checkContentHashes(deckContent));

  return issues;
}

/** sha256 prefix — must match decks/scripts/sync-hashes.mjs. */
function sha256(content: string): string {
  return createHash("sha256").update(content).digest("hex").slice(0, 16);
}

/**
 * Reads the recorded `<!-- sync: <name>=<hash> -->` comments in the deck,
 * recomputes every artifact hash, and flags stale, removed, or unrecorded
 * artifacts. An unrecorded artifact means the deck was not rebuilt.
 */
function checkContentHashes(deckContent: string): string[] {
  const issues: string[] = [];
  const re = /<!-- sync: ([^=]+)=([0-9a-f]{16}) -->/g;
  let m: RegExpExecArray | null;
  const seen = new Set<string>();

  while ((m = re.exec(deckContent)) !== null) {
    const [, artifactName, recordedHash] = m;
    const name = artifactName.trim();
    if (seen.has(name)) continue;
    seen.add(name);

    const liveHash = computeLiveHash(name);
    if (liveHash === null) {
      // Artifact removed from disk but still recorded — stale reference.
      issues.push(`artifact '${name}' recorded in deck but no longer exists in .omp/`);
      continue;
    }
    if (liveHash !== recordedHash) {
      issues.push(`artifact '${name}' changed since deck was synced (hash mismatch) — run 'make build' in decks/`);
    }
  }

  for (const name of listLiveArtifactNames()) {
    if (!seen.has(name)) {
      issues.push(`artifact '${name}' has no sync hash — run 'make build' in decks/`);
    }
  }

  return issues;
}

/** Lists every artifact that the deck hash contract must cover. */
function listLiveArtifactNames(): string[] {
  const names: string[] = [];
  const sources: Array<{ dir: string; prefix?: string; suffix: string }> = [
    { dir: join(ompDir, "rules"), suffix: ".md" },
    { dir: join(ompDir, "hooks", "pre"), suffix: ".ts" },
    { dir: join(ompDir, "hooks", "post"), suffix: ".ts" },
    { dir: join(ompDir, "hooks", "lib"), prefix: "lib/", suffix: ".ts" },
  ];
  for (const { dir, prefix = "", suffix } of sources) {
    if (!existsSync(dir)) continue;
    for (const file of readdirSync(dir)) {
      if (file.endsWith(suffix)) names.push(`${prefix}${file}`);
    }
  }

  const astRulesDir = join(ompDir, "ast-grep", "rules");
  if (existsSync(astRulesDir)) {
    for (const entry of readdirSync(astRulesDir, { withFileTypes: true })) {
      if (entry.isDirectory()) names.push(`ast-grep/rules/${entry.name}/`);
    }
  }

  const extensionsDir = join(ompDir, "extensions");
  if (existsSync(extensionsDir)) {
    for (const entry of readdirSync(extensionsDir, { withFileTypes: true })) {
      if (entry.isDirectory()) names.push(`extensions/${entry.name}/`);
    }
  }
  return names;
}

/**
 * Computes the live sha256 prefix for a recorded artifact name.
 * Handles: rules/<file>.md, hooks/{pre,post,lib}/<file>.ts, ast-grep/rules/<dir>/
 * (combined yml content — matches sync-hashes.mjs).
 * Returns null when the artifact no longer exists.
 */
function computeLiveHash(name: string): string | null {
  // ast-grep/rules/<dir>/ form
  // extensions/<dir>/ form — combined .ts content, matching sync-hashes.mjs
  const extensionMatch = name.match(/^extensions\/([^/]+)\/$/);
  if (extensionMatch) {
    const dirPath = join(ompDir, "extensions", extensionMatch[1]);
    if (!existsSync(dirPath)) return null;
    const files = readdirSync(dirPath).filter((f: string) => f.endsWith(".ts")).sort();
    return sha256(files.map((f: string) => readFileSync(join(dirPath, f), "utf8")).join("\n"));
  }

  const astMatch = name.match(/^ast-grep\/rules\/([^/]+)\/$/);
  if (astMatch) {
    const dirPath = join(ompDir, "ast-grep", "rules", astMatch[1]);
    if (!existsSync(dirPath)) return null;
    const files = readdirSync(dirPath).filter((f: string) => f.endsWith(".yml")).sort();
    return sha256(files.map((f: string) => readFileSync(join(dirPath, f), "utf8")).join("\n"));
  }

  // rules/<file>.md and hooks/{pre,post,lib}/<file>.ts — recorded names
  // carry the full filename (e.g. backend-api-http.md), so use as-is.
  const candidates = [
    join(ompDir, "rules", name),
    join(ompDir, "hooks", "pre", name),
    join(ompDir, "hooks", "post", name),
    join(ompDir, "hooks", name),
  ];
  for (const p of candidates) {
    if (existsSync(p)) return sha256(readFileSync(p, "utf8"));
  }
  return null;
}

// Direct execution (make check-decks-sync): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-decks-sync.ts")) {
  const issues = checkDecksSyncSync();
  console.log("==> check-decks-sync");
  if (issues.length === 0) {
    console.log("    PASS: decks/harness-rules/slides.md mentions all rules, hooks, and AST rule dirs");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-decks-sync");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
