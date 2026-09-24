// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * The backend layer layout — one declaration, three derivations.
 *
 * `backend-domain.md` documents the folder structure and
 * `strict-backend-app-structure` blocks writes outside it, but until this file
 * the *shape* of each layer — which ones hold folder domains, which are flat —
 * lived only in prose and in one traversal helper's habit of descending a
 * level. Every hook that re-implemented the walk from the directory name alone
 * went blind the day a domain became a folder: measured at seven checks, one of
 * which (`relationship lazy=`) applied to zero of the ten relationships it
 * existed to guard.
 *
 * So the shape is a value, and three consumers derive from it instead of
 * restating it:
 *
 * - `strict-backend-app-structure` (write side) — which directories may exist,
 *   and how deep a file may sit in each;
 * - `layerFiles()` (read side) — the one traversal every scan uses;
 * - `check-omp-hooks` (meta) — rejects a hook that walks a layer by hand.
 *
 * `depth` is the number of directory levels a file may sit below the layer
 * root: `0` is flat (`routers/user.py`), `1` allows folder domains
 * (`models/batch/run.py` — "a domain folder holds table files, never more
 * folders"), `null` is unconstrained (`tests/` mirrors the layers and nests
 * fixtures deeper).
 */
export const APP_LAYERS: Record<string, { depth: 0 | 1 | null }> = {
  models: { depth: 1 },
  schemas: { depth: 1 },
  repositories: { depth: 1 },
  services: { depth: 1 },
  routers: { depth: 0 },
  dependencies: { depth: 0 },
  core: { depth: 0 },
  batch: { depth: 0 },
  tests: { depth: null },
};

/**
 * Every `.py` in one layer, one level of nesting deep, as paths relative to the
 * layer root: `user.py`, `batch/run.py`.
 *
 * One level is the whole convention, so the walk is fixed rather than read from
 * `APP_LAYERS` — a flat layer simply has no directories to descend into, and
 * `tests/` scans pass their own subtree. What the spec above adds is the write
 * gate and the meta-check; this function is the read side they both assume.
 */
export function layerFiles(layerDir: string): string[] {
  if (!existsSync(layerDir)) return [];
  const files: string[] = [];
  for (const entry of readdirSync(layerDir, { withFileTypes: true })) {
    if (entry.name === "__pycache__" || entry.name === "__init__.py") continue;
    if (entry.isDirectory()) {
      for (const inner of readdirSync(join(layerDir, entry.name))) {
        if (inner.endsWith(".py") && inner !== "__init__.py") files.push(`${entry.name}/${inner}`);
      }
    } else if (entry.name.endsWith(".py")) {
      files.push(entry.name);
    }
  }
  return files;
}

/**
 * Why a write at this depth is refused, or null when the layer allows it.
 *
 * `backend/app/routers/sub/x.py` passed the write gate before this existed: the
 * gate checked only that `routers` is a known directory, so the flat shape every
 * router scan assumes was enforced by nothing. A file two levels under `models/`
 * is the same defect one door down — the traversal descends exactly one level,
 * so a deeper file would be written and then seen by no check at all.
 */
export function layerDepthViolation(appRelative: string): string | null {
  const segments = appRelative.split("/");
  const layer = APP_LAYERS[segments[0]];
  if (layer === undefined || layer.depth === null) return null;
  const directoryDepth = segments.length - 2;
  if (directoryDepth <= layer.depth) return null;
  return layer.depth === 0
    ? `\`${segments[0]}/\` is a flat layer — its files sit at the layer root, and every scan of it assumes that`
    : `\`${segments[0]}/\` allows one folder level (a domain), never more — a deeper file is invisible to every layer scan`;
}

/**
 * The text between the bracket at `open` and the one that closes it.
 *
 * A Python call spans lines the way `ruff format` breaks it, and a reader
 * that stops at the first line ending in `)` stops inside the call — measured
 * on `relationship(primaryjoin=lambda: foreign(X.col)\n== Y.col,
 * ..., lazy=...)`: the `lazy=` check read one line and reported it missing on
 * seven of seventeen relationships that had it.
 */
export function balanced(content: string, open: number): string {
  let depth = 0;
  for (let i = open; i < content.length; i += 1) {
    if (content[i] === "(" || content[i] === "[" || content[i] === "{") depth += 1;
    else if (content[i] === ")" || content[i] === "]" || content[i] === "}") {
      depth -= 1;
      if (depth === 0) return content.slice(open + 1, i);
    }
  }
  return content.slice(open + 1);
}
