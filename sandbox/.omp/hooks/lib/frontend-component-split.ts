/**
 * Where one thing was written twice, checked mechanically.
 *
 * Three defects, each measured in this repo, and each a *shape written twice*
 * rather than an abstraction that is missing:
 *
 * | Rule | The defect it caught |
 * |---|---|
 * | one section per shape | the run panel grew a second status-plus-payload section for the failure case, above the inputs that produced it |
 * | one component per concept | two exports differing only in a flag |
 * | one screen per record | a `*EditPanel` beside the `*Panel` it shadows: two shapes for one row |
 *
 * **Two screens of the same type are not a defect here.** `BatchList` and
 * `UserList` share 93 of 117 normalised lines, and that is the standard, not
 * duplication to factor away — `BatchList`'s own comment says why: a generic
 * `<CrudList domain={…}>` hides the columns, the dialogs and the empty sentence
 * behind configuration, and the first screen that needs one exception forks it.
 * So this module never compares two files' bodies. It reads one file against
 * itself, and file *names* against each other. Shape may be copied between
 * screens; a shape may not be written twice inside one of them.
 *
 * ## The metric is the tag sequence, and it was measured
 *
 * Comparing normalised *lines* scored the real defect at 0.27 — the two result
 * sections printed different values, so almost no line matched. What repeats is
 * the **shape**: `Stack>Stack>Typography>Label>Payload` inside
 * `Stack>Divider>Stack>Typography>Label>Payload>Payload`. Subsequence
 * containment finds it.
 *
 * Containment alone reported three pairs in `IntegrationOperationFieldsEditor`,
 * all of the form `Stack>IconButton>Iconify>IconButton>Iconify` inside a longer
 * row: incidental, because a shape built only from primitives is a layout row and
 * not a section. A repeat is therefore only reported when the shared shape carries
 * at least two **named** components — anything outside `PRIMITIVE_TAGS`. With that
 * split the tree reports nothing and the defect reports itself.
 *
 * Verified against a synthetic second domain (`sections/vendor/`): a conforming
 * panel passes untouched, the same section written twice fires, and a
 * `*EditPanel` beside the panel it shadows fires — so none of this is bound to
 * the integration screens it was measured on.
 */

import { SRC_DIRECTORIES, readSources, stripComments } from "./frontend-source.ts";

/** Container tags a section is built from: the blocks worth comparing. */
const CONTAINER_TAGS = ["Stack", "Box", "Card"];

/**
 * Tags that carry no meaning of their own — layout, text, icons, separators.
 * A repeated shape made only of these is a row of controls, not a section.
 */
const PRIMITIVE_TAGS = new Set([
  "Stack", "Box", "Card", "Grid", "Fragment", "Divider", "Typography",
  "IconButton", "Iconify", "Button", "MenuItem", "Tooltip", "span", "Alert",
]);

/** Below this the shape is too small to be a section anyone recognises. */
const MIN_SHAPE_TAGS = 4;

/** A repeat needs this many named components in the shared shape to be one. */
const MIN_NAMED_TAGS = 2;

/** Two exports this alike are one component whose difference is a prop. */
const EXPORT_SIMILARITY = 0.85;

/** Below this an export is a helper, not a component worth comparing. */
const MIN_EXPORT_LINES = 6;

/**
 * Names that mean "the same record, a different door". Declared rather than
 * inferred: `List` beside `Detail` is a different screen *type*, not a mode.
 */
const MODE_WORDS = [
  "Create", "Edit", "Update", "New", "Read", "View", "Success", "Error", "Failure",
];

interface Block {
  start: number;
  end: number;
  shape: string[];
}

export function checkComponentSplitSync(): string[] {
  const issues: string[] = [];
  const labels: string[] = [];

  for (const root of [SRC_DIRECTORIES.components, SRC_DIRECTORIES.sections, SRC_DIRECTORIES.layouts]) {
    for (const file of readSources(root)) {
      if (!file.label.endsWith(".tsx")) continue;
      labels.push(file.label);
      const code = stripComments(file.content);
      issues.push(...checkRepeatedSection(file.label, code));
      issues.push(...checkTwinExports(file.label, code));
    }
  }

  issues.push(...checkModeTwinFiles(labels));
  return issues;
}

/** The same section shape, written twice in one file, a condition around each. */
function checkRepeatedSection(fileLabel: string, code: string): string[] {
  const blocks = containerBlocks(code).filter((block) => block.shape.length >= MIN_SHAPE_TAGS);
  for (let left = 0; left < blocks.length; left += 1) {
    for (let right = left + 1; right < blocks.length; right += 1) {
      if (nested(blocks[left], blocks[right])) continue;
      const [small, large] =
        blocks[left].shape.length <= blocks[right].shape.length
          ? [blocks[left], blocks[right]]
          : [blocks[right], blocks[left]];
      if (!isSubsequence(small.shape, large.shape)) continue;
      const named = small.shape.filter((tag) => !PRIMITIVE_TAGS.has(tag));
      if (new Set(named).size < MIN_NAMED_TAGS) continue;
      return [
        `${fileLabel}: two sibling sections are the same shape — ` +
          `${small.shape.join(">")} inside ${large.shape.join(">")}. Render one section and put ` +
          "the difference inside it, or a change reaches one copy and the screen shows both",
      ];
    }
  }
  return [];
}

/** Two exports whose bodies agree are one export with a prop. */
function checkTwinExports(fileLabel: string, code: string): string[] {
  const bodies = exportedBodies(code).filter(([, body]) => body.length >= MIN_EXPORT_LINES);
  for (let left = 0; left < bodies.length; left += 1) {
    for (let right = left + 1; right < bodies.length; right += 1) {
      const score = similarity(bodies[left][1], bodies[right][1]);
      if (score < EXPORT_SIMILARITY) continue;
      return [
        `${fileLabel}: ${bodies[left][0]} and ${bodies[right][0]} are ` +
          `${(score * 100).toFixed(0)}% the same component — keep one and take the ` +
          "difference as a prop",
      ];
    }
  }
  return [];
}

/** `XEditPanel` beside `XPanel`: one record, two doors. */
function checkModeTwinFiles(labels: string[]): string[] {
  const issues: string[] = [];
  const byStem = new Map<string, string[]>();
  for (const label of labels) {
    const name = label.split("/").pop() ?? "";
    // The plain name is a stem too: `XPanel.tsx` plus `XEditPanel.tsx` is the pair
    // this rule exists for, and grouping only stripped names left the mode file
    // alone in its group and the check silent.
    byStem.set(name, [...(byStem.get(name) ?? []), label]);
    for (const word of MODE_WORDS) {
      if (!name.includes(word)) continue;
      const stem = name.replace(word, "");
      byStem.set(stem, [...(byStem.get(stem) ?? []), label]);
    }
  }
  for (const [, files] of byStem) {
    if (files.length < 2) continue;
    issues.push(
      `${[...new Set(files)].sort().join(" and ")}: two files for one record's modes — one ` +
        "screen holds the record and takes the mode as state, so reading and editing cannot " +
        "drift into two shapes for the same row",
    );
  }
  return issues;
}

function normalizedLines(source: string): string[] {
  return source
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 3);
}

function similarity(left: string[], right: string[]): number {
  const a = new Set(left);
  const b = new Set(right);
  let shared = 0;
  for (const line of a) if (b.has(line)) shared += 1;
  return shared / (a.size + b.size - shared);
}

/** Balanced `<Tag …>…</Tag>` regions, with the JSX tag sequence each one draws. */
function containerBlocks(code: string): Block[] {
  const blocks: Block[] = [];
  for (const tag of CONTAINER_TAGS) {
    const opening = new RegExp(`<${tag}\\b`, "g");
    let match = opening.exec(code);
    while (match !== null) {
      const end = blockEnd(code, match.index, tag);
      if (end > 0) {
        blocks.push({ start: match.index, end, shape: tagSequence(code.slice(match.index, end)) });
      }
      match = opening.exec(code);
    }
  }
  return blocks;
}

function blockEnd(code: string, start: number, tag: string): number {
  const opening = new RegExp(`<${tag}\\b`, "g");
  const closing = new RegExp(`</${tag}>`, "g");
  opening.lastIndex = start + 1;
  closing.lastIndex = start;
  let depth = 1;
  let nextOpen = opening.exec(code);
  let nextClose = closing.exec(code);
  while (nextClose !== null) {
    if (nextOpen !== null && nextOpen.index < nextClose.index) {
      depth += 1;
      opening.lastIndex = nextOpen.index + 1;
      nextOpen = opening.exec(code);
      continue;
    }
    depth -= 1;
    if (depth === 0) return nextClose.index + tag.length + 3;
    closing.lastIndex = nextClose.index + 1;
    nextClose = closing.exec(code);
  }
  return -1;
}

/** The components a block draws, in source order — its shape, not its content. */
function tagSequence(block: string): string[] {
  return [...block.matchAll(/<([A-Z][A-Za-z0-9]*)/g)].map((match) => match[1]);
}

function nested(left: Block, right: Block): boolean {
  return (
    (left.start <= right.start && right.end <= left.end) ||
    (right.start <= left.start && left.end <= right.end)
  );
}

function isSubsequence(small: string[], large: string[]): boolean {
  let index = 0;
  for (const tag of large) {
    if (tag === small[index]) index += 1;
    if (index === small.length) return true;
  }
  return false;
}

/**
 * Exported function components with their bodies.
 *
 * Brace-balanced from the declaration, because a component's body contains lines
 * that start with `}` at every indent — reading to the first one stopped inside
 * the props destructuring and made every export look alike.
 */
function exportedBodies(code: string): Array<[string, string[]]> {
  const bodies: Array<[string, string[]]> = [];
  const declaration = /export\s+(?:default\s+)?function\s+(\w+)\s*\(/g;
  let match = declaration.exec(code);
  while (match !== null) {
    const bodyStart = code.indexOf("{", match.index + match[0].length - 1);
    if (bodyStart > 0) {
      let depth = 0;
      let cursor = bodyStart;
      while (cursor < code.length) {
        if (code[cursor] === "{") depth += 1;
        else if (code[cursor] === "}") {
          depth -= 1;
          if (depth === 0) break;
        }
        cursor += 1;
      }
      bodies.push([match[1], normalizedLines(code.slice(bodyStart, cursor))]);
    }
    match = declaration.exec(code);
  }
  return bodies;
}
