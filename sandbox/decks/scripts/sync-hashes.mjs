#!/usr/bin/env node
// Insert/refresh `<!-- sync: <name>=<sha256> -->` comments into deck sources.
// Each comment records the content hash of a harness artifact (rule file,
// hook file, including shared hook libraries, or AST rule dir).
// check-decks-sync.ts compares these hashes against the live files — a mismatch
// means the deck is stale.
//
// Usage: node scripts/sync-hashes.mjs <deck-dir> [more...]
// Run from decks/ (make build does this automatically).
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, ".omp")) ? cwd : join(cwd, "..");
const ompDir = join(projectRoot, ".omp");

function sha256(content) {
  return createHash("sha256").update(content).digest("hex").slice(0, 16);
}

/** Collect every harness artifact with its content hash. */
function collectArtifacts() {
  const artifacts = [];

  const rulesDir = join(ompDir, "rules");
  if (existsSync(rulesDir)) {
    for (const f of readdirSync(rulesDir).sort()) {
      if (!f.endsWith(".md")) continue;
      artifacts.push({ name: f, hash: sha256(readFileSync(join(rulesDir, f), "utf8")) });
    }
  }

  for (const sub of ["pre", "post"]) {
    const dir = join(ompDir, "hooks", sub);
    if (!existsSync(dir)) continue;
    for (const f of readdirSync(dir).sort()) {
      if (!f.endsWith(".ts")) continue;
      artifacts.push({ name: f, hash: sha256(readFileSync(join(dir, f), "utf8")) });
    }
  }

  const libDir = join(ompDir, "hooks", "lib");
  if (existsSync(libDir)) {
    for (const f of readdirSync(libDir).sort()) {
      if (!f.endsWith(".ts")) continue;
      artifacts.push({ name: `lib/${f}`, hash: sha256(readFileSync(join(libDir, f), "utf8")) });
    }
  }

  const astRulesDir = join(ompDir, "ast-grep", "rules");
  if (existsSync(astRulesDir)) {
    for (const d of readdirSync(astRulesDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (!d.isDirectory()) continue;
      const dirPath = join(astRulesDir, d.name);
      const files = readdirSync(dirPath).filter((f) => f.endsWith(".yml")).sort();
      const combined = files.map((f) => readFileSync(join(dirPath, f), "utf8")).join("\n");
      artifacts.push({ name: `ast-grep/rules/${d.name}/`, hash: sha256(combined) });
    }
  }

  const extensionsDir = join(ompDir, "extensions");
  if (existsSync(extensionsDir)) {
    for (const d of readdirSync(extensionsDir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (!d.isDirectory()) continue;
      const dirPath = join(extensionsDir, d.name);
      const files = readdirSync(dirPath).filter((f) => f.endsWith(".ts")).sort();
      const combined = files.map((f) => readFileSync(join(dirPath, f), "utf8")).join("\n");
      artifacts.push({ name: `extensions/${d.name}/`, hash: sha256(combined) });
    }
  }

  return artifacts;
}

/** Replace the sync comment block in a deck source. */
function syncDeck(deckPath) {
  if (!existsSync(deckPath)) {
    console.error(`SKIP (deck not found): ${deckPath}`);
    return;
  }
  const artifacts = collectArtifacts();
  const block = artifacts.map((a) => `<!-- sync: ${a.name}=${a.hash} -->`).join("\n");

  let content = readFileSync(deckPath, "utf8");
  // Remove any existing sync comments (single-line form).
  content = content.replace(/<!-- sync: [^\n]* -->\n?/g, "");
  // Insert after the headmatter (--- ... ---) so it never lands inside a slide.
  const headmatter = content.match(/^---\n[\s\S]*?\n---\n/);
  if (headmatter) {
    content = content.slice(0, headmatter[0].length) + block + "\n" + content.slice(headmatter[0].length);
  } else {
    content = block + "\n" + content;
  }
  writeFileSync(deckPath, content);
  console.log(`SYNCED: ${deckPath} (${artifacts.length} artifacts)`);
}

for (const deckDir of process.argv.slice(2)) {
  syncDeck(join(deckDir, "slides.md"));
}
