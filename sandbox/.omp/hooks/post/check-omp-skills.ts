import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, resetSuppression, wrapWarning } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";

declare const process: {
  argv: string[];
  cwd(): string;
  exitCode?: number;
};

/**
 * Check-OMP-Skills Post Hook
 *
 * Validates the bidirectional contract between the managed skills catalog in
 * .omp/rules/omp-skills.md and native skill discovery at
 * .omp/skills/<name>/SKILL.md. Runtime discovery remains file-backed; the
 * catalog provides the trigger, verification, and lifecycle metadata.
 */
const cwd = process.cwd();
const skillsDir = join(cwd, ".omp", "skills");
const catalogPath = join(cwd, ".omp", "rules", "omp-skills.md");
const CATALOG_HEADER = "| Skill | Trigger | Verification | Lifecycle (project metadata) |";

/** Read-only tools never change skills or their catalog. */
const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


interface CatalogRow {
  trigger: string;
  verification: string;
  lifecycle: string;
}

export default function checkOmpSkills(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-omp-skills", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkOmpSkillsSync();
    if (issues.length === 0) {
      resetSuppression("check-omp-skills");
      return;
    }

    const warning = buildSafeWarning(
      event.toolName,
      "check-omp-skills",
      issues,
      "update .omp/rules/omp-skills.md and .omp/skills/<name>/SKILL.md together",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-omp-skills") };
  }));
}

export function checkOmpSkillsSync(): string[] {
  const issues: string[] = [];
  const catalog = readCatalog(issues);
  const discovered = readDiscoveredSkills(issues);

  for (const [name, row] of catalog) {
    if (!row.trigger) issues.push(`catalog row '${name}' has an empty Trigger`);
    if (!row.verification) issues.push(`catalog row '${name}' has an empty Verification`);
    if (row.lifecycle !== "active" && row.lifecycle !== "deprecated") {
      issues.push(`catalog row '${name}' has invalid Lifecycle '${row.lifecycle}' (use active or deprecated)`);
    }
    if (!discovered.has(name)) {
      issues.push(`catalog row '${name}' has no matching .omp/skills/${name}/SKILL.md`);
    }
  }

  for (const name of discovered) {
    if (!catalog.has(name)) {
      issues.push(`skill '${name}' is missing from the Skill Catalog table`);
    }
  }

  return issues;
}

function readCatalog(issues: string[]): Map<string, CatalogRow> {
  const catalog = new Map<string, CatalogRow>();
  if (!existsSync(catalogPath)) {
    issues.push(".omp/rules/omp-skills.md not found");
    return catalog;
  }

  const lines = readFileSync(catalogPath, "utf-8").split(/\r?\n/);
  let inCatalog = false;
  let foundSection = false;
  let foundHeader = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("## ")) {
      inCatalog = trimmed === "## Skill Catalog";
      foundSection ||= inCatalog;
      continue;
    }
    if (!inCatalog || !trimmed.startsWith("|")) continue;
    if (trimmed === CATALOG_HEADER) {
      foundHeader = true;
      continue;
    }
    if (/^\|\s*-+\s*\|/.test(trimmed)) continue;
    if (/^\|\s*Skill\s*\|/.test(trimmed)) {
      issues.push(`Skill Catalog must use header: ${CATALOG_HEADER}`);
      continue;
    }

    const cells = trimmed.match(/^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$/);
    if (!cells) {
      issues.push(`invalid Skill Catalog row: ${trimmed}`);
      continue;
    }
    const [, name, trigger, verification, lifecycle] = cells;
    if (catalog.has(name)) {
      issues.push(`Skill Catalog contains duplicate row '${name}'`);
      continue;
    }
    catalog.set(name, { trigger, verification, lifecycle });
  }

  if (!foundSection) issues.push("missing '## Skill Catalog' section in .omp/rules/omp-skills.md");
  if (!foundHeader) issues.push(`.omp/rules/omp-skills.md: Skill Catalog header must be ${CATALOG_HEADER}`);
  return catalog;
}

function readDiscoveredSkills(issues: string[]): Set<string> {
  const discovered = new Set<string>();
  if (!existsSync(skillsDir)) {
    issues.push(".omp/skills/ directory not found");
    return discovered;
  }

  for (const entry of readdirSync(skillsDir, { withFileTypes: true }).sort(
    (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name),
  )) {
    if (!entry.isDirectory()) continue;
    const skillPath = join(skillsDir, entry.name, "SKILL.md");
    if (!existsSync(skillPath)) continue;

    const frontmatter = readFrontmatter(readFileSync(skillPath, "utf-8"));
    if (!frontmatter) {
      issues.push(`skill '${entry.name}' is missing YAML frontmatter`);
      continue;
    }
    const name = fieldValue(frontmatter, "name");
    const description = fieldValue(frontmatter, "description");
    if (!name) {
      issues.push(`skill '${entry.name}' is missing frontmatter name`);
      continue;
    }
    if (name !== entry.name) {
      issues.push(`skill '${entry.name}' frontmatter name must equal directory name (found '${name}')`);
      continue;
    }
    if (!description) issues.push(`skill '${entry.name}' is missing frontmatter description`);
    discovered.add(name);
  }

  return discovered;
}

function readFrontmatter(content: string): string | null {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  return match?.[1] ?? null;
}

function fieldValue(frontmatter: string, field: string): string {
  const match = frontmatter.match(new RegExp(`^${field}:\\s*(.+?)\\s*$`, "m"));
  return match?.[1]?.trim() ?? "";
}

// Direct execution (make check-omp-skills): run the same check on demand.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-omp-skills.ts")) {
  const issues = checkOmpSkillsSync();
  console.log("==> check-omp-skills");
  if (issues.length === 0) {
    console.log("    PASS: skills catalog matches discovered SKILL.md files");
  } else {
    for (const issue of issues) console.error(`    FAIL: ${issue}`);
    process.exitCode = 1;
  }
}
