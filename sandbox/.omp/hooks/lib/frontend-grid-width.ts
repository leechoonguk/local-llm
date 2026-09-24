// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join, relative } from "node:path";
import { resolveProjectRoot } from "./hook-project-root.ts";
import { parseLocaleValues } from "./frontend-i18n.ts";

/**
 * Grid columns wide enough for what they print.
 *
 * A column is a floor (`minWidth`) and a share (`flex`), and the floor is what
 * the reader gets on a full screen. Two things in a cell cannot shrink: a
 * **badge** (`Label` sets `white-space: nowrap`, so a narrow column cuts it
 * mid-word behind the cell's overflow) and a **header name** (the grid
 * ellipsises it, and a header nobody can read is a column nobody can sort).
 * Everything else is prose the tooltip completes.
 *
 * Measured in the running app at 1440px: a kind badge needs 124px
 * of column and had 90 - every row of `/food/item-report` showed a cut label;
 * `등급 · 기관` needed 58px of title and had 55. Both passed every gate, because
 * nothing compared a number in the column table with the text the locale holds.
 *
 * So the comparison is made here, from the two files that already hold both
 * facts - the column table and the locale - with no browser and no guess about
 * what the reader will see:
 *
 * | ink | source |
 * | --- | --- |
 * | header | `headerName: t('<key>')` → the locale's longest reading |
 * | badge | the column's declared `badges` prefix → every value under it |
 *
 * The per-character ink is the font's own, measured through the canvas API in
 * the running app: the grid header at `600 14px Public Sans` and a
 * badge at `700 12px`. A Hangul syllable is one em, the Latin letters two
 * thirds of one, and the model rounds each class up, so the check is
 * conservative by construction - it asks for a pixel or two more than the
 * browser needs and never for less.
 */

const projectRoot = resolveProjectRoot();

const sectionsDir = join(projectRoot, "frontend", "src", "sections");

const localesDir = join(projectRoot, "frontend", "src", "locales");

/** Per-character ink at the grid header's font (`600 14px`), by character class. */
const HEADER_INK = { cjk: 12.2, upper: 9.9, lower: 8.2, digit: 8.2, narrow: 3.6 };

/** Per-character ink at a badge's font (`700 12px`). */
const BADGE_INK = { cjk: 10.4, upper: 8.4, lower: 7.0, digit: 7.3, narrow: 3.2 };

/** The grid's own cell padding, left plus right (measured: 20px each side). */
const CELL_PADDING = 40;

/** A badge's padding, left plus right (`theme.spacing(0, 1)`). */
const BADGE_PADDING = 16;

/**
 * The room the sort arrow takes beside a header name. MUI renders it inside the
 * header cell, so a title sized to its own ink alone loses its last character
 * the moment the column is sortable.
 */
const SORT_ICON = 24;

/**
 * The pixels a dialog table's percentage is a percentage *of*.
 *
 * A record dialog opens at `RECORD_SURFACE.DIALOG_MAX_WIDTH` and its tables
 * divide `RECORD_SURFACE.TABLE_WIDTH` - the paper less the dialog's 24px sides
 * and the card's 16px. Read from the config rather than repeated here, so
 * widening the surface moves both the screen and this reading at once.
 */
const DIALOG_TABLE_WIDTH = tableWidth();

/** The pixels a dialog table divides, as the frontend's own config states them. */
function tableWidth(): number {
  const config = join(projectRoot, "frontend", "src", "config.ts");
  if (!existsSync(config)) return 0;
  const declared = /TABLE_WIDTH:\s*(\d+)/.exec(readFileSync(config, "utf-8"));
  return declared === null ? 0 : Number(declared[1]);
}

/** A table cell's padding, left plus right (MUI's default 16px each side). */
const TABLE_CELL_PADDING = 32;


// ============================================================
// Functions
// ============================================================

/**
 * Section cards stand at one gap, and the gap has a name.
 *
 * `DetailSection` and `PagedTableSection` are the cards of a record surface, and
 * the gap between two of them belongs to the parent that stacks them. Measured
 * across the report dialog's seven tabs: the standards tab stacked at
 * 3 (24px), the nutrition and label tabs at 2 (16px), and the record tab
 * rendered its cards straight into the dialog body with no stack at all - the
 * same reader saw three different rhythms by switching tabs.
 *
 * So a card is stacked by `<Stack spacing={RECORD_SURFACE.SECTION_GAP}>` and by
 * nothing else: a bare number on the stack that wraps a card is refused even
 * when it happens to equal today's value, because the next reader copies the
 * number and not the decision.
 */
export function checkSectionGaps(): string[] {
  const issues: string[] = [];
  if (!existsSync(sectionsDir)) return issues;
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const file = `src/sections/${relative(sectionsDir, path)}`;
    const cards = [...content.matchAll(/<(DetailSection|PagedTableSection)\b/g)];
    if (cards.length === 0) continue;
    for (const card of cards) {
      const stack = enclosingStack(content, card.index);
      if (stack === null) {
        // A `return` that draws one card has no gap to get wrong - the empty
        // state of a tab is that shape, and the dialog body it lands in is the
        // stack. The rule is about siblings.
        if (!hasSiblingCard(content, card.index)) continue;
        issues.push(
          `${file}: a <${card[1]}> is drawn with no stack around it - two cards then touch, ` +
            "while a sibling tab's stand 24px apart; wrap them in " +
            "<Stack spacing={RECORD_SURFACE.SECTION_GAP}>",
        );
        continue;
      }
      if (stack === "none") continue;
      if (stack !== "RECORD_SURFACE.SECTION_GAP") {
        issues.push(
          `${file}: a <${card[1]}> is stacked at spacing={${stack}} - the gap between record ` +
            "cards is RECORD_SURFACE.SECTION_GAP, named once so every tab reads at one rhythm",
        );
      }
    }
  }
  return issues;
}

/** Whether another card is drawn by the same `return` as the one at this offset. */
function hasSiblingCard(content: string, offset: number): boolean {
  const start = content.lastIndexOf("return (", offset);
  if (start === -1) return true;
  // The block ends at its own closing parenthesis, whatever it is indented by:
  // an early return inside an `if` closes at four spaces and the function's at
  // two, and reading to the wrong one swallowed the next return whole.
  const rest = content.slice(offset);
  const close = /\n\s{0,6}\)\s*\n/.exec(rest);
  const block = content.slice(start, close === null ? content.length : offset + close.index);
  const cards = [...block.matchAll(/<(DetailSection|PagedTableSection)\b/g)].length;
  return cards > 1 || /\.map\(/.test(block);
}

/** The `spacing` of the nearest `<Stack>` still open above an offset. */
function enclosingStack(content: string, offset: number): string | null {
  const before = content.slice(0, offset);
  let depth = 0;
  for (let index = before.length - 1; index >= 0; index -= 1) {
    if (before.startsWith("</Stack>", index)) depth += 1;
    else if (before.startsWith("<Stack", index)) {
      if (depth > 0) {
        depth -= 1;
        continue;
      }
      const tag = content.slice(index, content.indexOf(">", index) + 1);
      const spacing = /spacing=\{([^}]*(?:\{[^}]*\})?[^}]*)\}/.exec(tag);
      return spacing === null ? "none" : spacing[1];
    }
  }
  return null;
}

/**
 * A count is drawn when there is something to count, and a date is drawn as a date.
 *
 * Two readings that generalise past the screen they were found on
 * (the product dialog):
 *
 * - **A zero is not information.** The dialog drew "신고 건수 0 / 사건 건수 0"
 *   on every product - 227 of 1,978,865 products carry an event, so that card
 *   said "0" 99.99 % of the time and the 227 that mattered were below it. A
 *   `*_count` is rendered under a `> 0` guard or not at all.
 * - **A portal date is eight digits.** The registries publish `20260915` and the
 *   ledger stores it verbatim, which is right for a ledger; a screen that prints
 *   it makes the reader count characters. A field holding a `*_date` goes
 *   through `formatPortalDate`.
 */
export function checkScreenValues(): string[] {
  const issues: string[] = [];
  if (!existsSync(sectionsDir)) return issues;
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const file = `src/sections/${relative(sectionsDir, path)}`;
    for (const [index, line] of content.split("\n").entries()) {
      if (/^\s*(\/\/|\*)/.test(line)) continue;
      // A locale key ends in `_count` too (`standards.individual_count`), and a
      // line that *is* the guard names the count by definition. Neither is a
      // count drawn on the screen.
      const count = /(?<!['"`.\w])(?:report|row|record|data)\??\.(\w+_count)\b/.exec(line);
      const isGuard = count !== null && new RegExp(`${count[1]}\\s*(?:>|===|!==|&&|\\?)`).test(line);
      if (count !== null && !isGuard && !guardedAbove(content, index, count[1])) {
        issues.push(
          `${file}:${index + 1}: draws ${count[1]} with no "> 0" guard - a count of zero is a ` +
            "line that says nothing, and the rows that matter are below it",
        );
      }
      // A line that names a formatter is already reading the date; what this
      // refuses is the raw field handed straight to a cell.
      const formatted = /format\w*\(/.test(line);
      const date = /<(?:ClippedText text|DetailField[^>]*)>?[^<]*\{[^}]*\.(\w*_date)\b/.exec(line);
      if (date !== null && !formatted) {
        issues.push(
          `${file}:${index + 1}: prints ${date[1]} as the registry wrote it - eight digits are a ` +
            "ledger's spelling; a screen reads them through formatPortalDate",
        );
      }
    }
  }
  return issues;
}

/**
 * Whether the JSX block that draws this line is guarded on the same count.
 *
 * The block, not a window of lines: a sibling block above may guard the same
 * count, and reading a fixed number of lines back called that a guard (measured
 * while writing this - a count drawn in the summary card passed because the
 * event card twelve lines up was guarded).
 */
function guardedAbove(content: string, index: number, field: string): boolean {
  const lines = content.split("\n");
  let start = 0;
  for (let cursor = index; cursor >= 0; cursor -= 1) {
    if (/^\s{2,}\{\w[\w.?]*\s*(?:!==|===|&&)/.test(lines[cursor] ?? "")) {
      start = cursor;
      break;
    }
  }
  const block = lines.slice(start, index + 1).join("\n");
  return new RegExp(`${field}\\s*>\\s*0`).test(block);
}

/**
 * A date column reads as a date, in a grid as well as in a record.
 *
 * `checkScreenValues` already refuses a raw `*_date` handed to `ClippedText` or
 * `DetailField`, and that is exactly how it missed a grid: a list declares a
 * column and `ServerDataGrid` injects the cell, so the raw value never appears
 * beside a component name. Measured after the check existed - `/food/item-report`
 * printed `20260915` in 보고일자 and the 사건 list did the same in 등록일, with
 * every gate green.
 *
 * Two spellings, one per storage: a `*_date` is a registry's eight digits
 * (`formatPortalDate`), a `*_at` is a timestamp this database wrote
 * (`formatDateTime`). The column may format in `valueFormatter` or in
 * `renderCell` - what is refused is a column that formats nowhere.
 */
export function checkGridDateColumns(): string[] {
  if (!existsSync(sectionsDir)) return [];
  const issues: string[] = [];
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const file = `src/sections/${relative(sectionsDir, path)}`;
    for (const column of columnBodies(content)) {
      const formatter = column.field.endsWith("_date")
        ? "formatPortalDate"
        : column.field.endsWith("_at")
          ? "formatDateTime"
          : null;
      if (formatter === null) continue;
      if (column.body.includes(formatter)) continue;
      issues.push(
        `${file}: column ${column.field} prints the stored value - a grid cell reads it ` +
          `through ${formatter}, in valueFormatter or renderCell`,
      );
    }
  }
  return issues;
}

/**
 * No two columns of one grid carry the same header.
 *
 * A header is the only name a column has, so two columns reading 구분 leave the
 * reader to guess which is the authority's action and which is the registry the
 * product is in - measured on the 사건 list, where `event_kind` and `report_kind`
 * both resolved to 구분 and every gate was green because each key existed and
 * each was translated.
 *
 * Read per locale rather than through the widest reading: two columns may
 * collide in Korean and not in English, and a collision in either is a screen
 * somebody reads.
 *
 * And read inside the **file's own namespace**. A key is written as the screen
 * writes it (`t('table.code')`), and the same tail exists under several
 * namespaces - measured while testing this check on the batch list, where
 * `table.code` resolved to the raw material ledger's 원재료 코드 instead of the
 * schedule's 잡 코드. A tail that no bound namespace answers is skipped rather
 * than guessed at: reporting a collision between two labels the screen never
 * shows is worse than reporting none.
 */
export function checkGridHeaderCollisions(): string[] {
  if (!existsSync(sectionsDir) || !existsSync(localesDir)) return [];
  const issues: string[] = [];
  const byLocale = localeValuesByLocale();
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const file = `src/sections/${relative(sectionsDir, path)}`;
    const namespaces = boundNamespaces(content);
    for (const [locale, labels] of byLocale) {
      const seen = new Map<string, string>();
      for (const column of columnDefinitions(content)) {
        for (const key of column.headerKeys) {
          const label = resolve(labels, namespaces, key);
          if (label === undefined) continue;
          const owner = seen.get(label);
          if (owner === undefined) {
            seen.set(label, column.field);
            continue;
          }
          if (owner === column.field) continue;
          issues.push(
            `${file}: columns ${owner} and ${column.field} are both headed "${label}" ` +
              `in ${locale} - a header is the column's only name`,
          );
        }
      }
    }
  }
  return issues;
}

/**
 * The namespaces a file's `t` aliases are bound to, in the order they appear.
 *
 * `useTranslation('batch')` and `useTranslation('common')` both answer keys on
 * one screen, so a header's key is looked for under each before the bare tail.
 */
function boundNamespaces(content: string): string[] {
  return [...content.matchAll(/useTranslation\(\s*'(\w+)'\s*\)/g)].map((hit) => hit[1]);
}

/** One header key's label, resolved the way the screen resolves it. */
function resolve(
  labels: Map<string, string>,
  namespaces: string[],
  key: string,
): string | undefined {
  for (const namespace of namespaces) {
    const value = labels.get(`${namespace}.${key}`);
    if (value !== undefined) return value;
  }
  return undefined;
}

/** Every `{ ...sized('field'), … }` block with the source it spans. */
function columnBodies(content: string): { field: string; body: string }[] {
  const found: { field: string; body: string }[] = [];
  for (const match of content.matchAll(/\.\.\.sized\('([a-z0-9_]+)'\)/g)) {
    const next = content.indexOf("...sized('", match.index + 1);
    found.push({
      field: match[1],
      body: content.slice(match.index, next === -1 ? content.length : next),
    });
  }
  return found;
}

/** Each locale's own values, keyed the way a screen writes them. */
function localeValuesByLocale(): Map<string, Map<string, string>> {
  const byLocale = new Map<string, Map<string, string>>();
  for (const file of readdirSync(localesDir)) {
    if (!file.endsWith(".ts") || file.endsWith(".d.ts") || file === "i18n.ts") continue;
    const values = new Map<string, string>();
    for (const [key, value] of parseLocaleValues(readFileSync(join(localesDir, file), "utf-8"))) {
      const parts = key.split(".");
      for (let index = 0; index < parts.length; index += 1) {
        values.set(parts.slice(index).join("."), value);
      }
    }
    byLocale.set(file.replace(/\.ts$/, ""), values);
  }
  return byLocale;
}

/** Every column whose floor is narrower than what the column prints. */
export function checkGridColumnWidths(): string[] {
  if (!existsSync(sectionsDir) || !existsSync(localesDir)) return [];
  const labels = localeValues();
  const issues: string[] = [];
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const floors = columnFloors(content);
    if (floors.size === 0) continue;
    const file = `src/sections/${relative(sectionsDir, path)}`;
    // The same pairing the dialog tables are held to: a `COLUMN` entry whose
    // definition this scanner never finds is a column measured by nothing, and
    // silence there reads exactly like a column that fits.
    const defined = new Set(columnDefinitions(content).map((column) => column.field));
    const unread = [...floors.keys()].filter((field) => !defined.has(field));
    if (unread.length > 0) {
      issues.push(
        `${file}: ${unread.join(", ")} floor in COLUMN but no column definition was read for ` +
          "them - the columns are written in a form this check does not parse, so their headers " +
          "and badges are unmeasured",
      );
      continue;
    }
    for (const column of columnDefinitions(content)) {
      const floor = floors.get(column.field);
      if (floor === undefined) continue;
      const header = longest(labels, column.headerKeys);
      if (header !== null) {
        const needed = Math.ceil(ink(header, HEADER_INK) + CELL_PADDING + SORT_ICON);
        if (floor < needed) {
          issues.push(
            `${file}: column '${column.field}' floors at ${floor}px but its header ` +
              `'${header}' needs ${needed}px - the grid ellipsises a title that does not fit`,
          );
        }
      }
      if (column.badgeKeys.length === 0) continue;
      const keys = column.badgeKeys.flatMap((key) =>
        key.endsWith(".*") ? keysUnder(labels, key.slice(0, -2)) : [key],
      );
      const badge = longest(labels, keys);
      if (badge === null) continue;
      const needed = Math.ceil(ink(badge, BADGE_INK) + BADGE_PADDING + CELL_PADDING);
      if (floor < needed) {
        issues.push(
          `${file}: column '${column.field}' floors at ${floor}px but the badge '${badge}' needs ` +
            `${needed}px - a badge sets white-space: nowrap, so the cell cuts it mid-word`,
        );
      }
    }
  }
  issues.push(...checkDialogTableWidths(labels));
  return issues;
}

/**
 * The same reading for a dialog's table, whose columns are percentages.
 *
 * A record dialog states its columns as `{ key, label: t('…'), width: 'NN%' }`
 * and renders the row's cells positionally beside them, so the badge a cell
 * prints belongs to the column at its index. The paper is a fixed width, which
 * is what turns a percentage back into the pixels a reader gets.
 */
function checkDialogTableWidths(labels: Map<string, string>): string[] {
  const issues: string[] = [];
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const file = `src/sections/${relative(sectionsDir, path)}`;
    // The key is camelCase as often as it is snake (`rotationGroup`, `createdAt`,
    // `fieldCount`): reading only the lower-case form dropped three columns from
    // two tables, silently, and the pairing check below is what said so.
    const columns = [...content.matchAll(/\{\s*key: '(\w+)',\s*label: (t\w*\('([^']+)'\)),\s*width: '(\d+)%'/g)];
    if (columns.length === 0) continue;
    const cells = cellExpressions(content);
    // Both halves or neither. A file that declares columns and whose cells this
    // scanner reads a different number of is the shape that hid a clipped badge
    // behind a green gate for as long as `renderCells` existed: `cells[index]`
    // came back undefined and every badge check quietly skipped. "I could not
    // read it" is a different answer from "there is nothing wrong with it", and
    // only one of them may pass.
    if (cells.length !== columns.length) {
      issues.push(
        `${file}: ${columns.length} dialog columns declared but ${cells.length} cells read - ` +
          "the table is written in a form this check does not parse, so every badge in it is " +
          "unmeasured. Teach the scanner the form or write the table in the existing one",
      );
      continue;
    }
    for (const [index, column] of columns.entries()) {
      const width = Math.floor((Number(column[4]) / 100) * DIALOG_TABLE_WIDTH);
      const header = longest(labels, [column[3]]);
      if (header !== null) {
        const needed = Math.ceil(ink(header, HEADER_INK) + TABLE_CELL_PADDING);
        if (width < needed) {
          issues.push(
            `${file}: dialog column '${column[1]}' is ${column[4]}% (${width}px) but its header ` +
              `'${header}' needs ${needed}px - a table header wraps or clips, never shrinks`,
          );
        }
      }
      const cell = cells[index];
      if (cell === undefined || !cell.includes("<Label")) continue;
      const prefix = /t\(`([^`$]+)\$\{/.exec(cell);
      const keys = prefix === null
        ? [...cell.matchAll(/t\w*\('([^']+)'\)/g)].map((hit) => hit[1])
        : keysUnder(labels, prefix[1].replace(/\.$/, ""));
      const badge = longest(labels, keys);
      if (badge === null) continue;
      const needed = Math.ceil(ink(badge, BADGE_INK) + BADGE_PADDING + TABLE_CELL_PADDING);
      if (width < needed) {
        issues.push(
          `${file}: dialog column '${column[1]}' is ${column[4]}% (${width}px) but the badge ` +
            `'${badge}' needs ${needed}px - a badge sets white-space: nowrap`,
        );
      }
    }
  }
  return issues;
}

/**
 * A dialog table's cells, in column order, in either shape the codebase writes.
 *
 * `PagedTableSection` takes `cells={(row) => [ … ]}` - an array, one element per
 * column - and `ServerPagedTable` takes `renderCells={(row) => (<>…</>)}`, a
 * fragment of `<TableCell>` elements. Only the array was read, so every badge in
 * a `renderCells` table went unmeasured: the 사용 제품 table floors 구분 at 12 %
 * (133px) and `Health functional food` needs 196, which is why it drew clipped through
 * a green gate.
 */
function cellExpressions(content: string): string[] {
  const array = /cells=\{\([^)]*\)\s*=>\s*\[/.exec(content);
  if (array === null) return jsxCellExpressions(content);
  const start = array;
  let depth = 0;
  let current = "";
  const found: string[] = [];
  for (let index = start.index + start[0].length; index < content.length; index += 1) {
    const character = content[index];
    if ("([{<".includes(character)) depth += 1;
    else if (")]}>".includes(character)) {
      if (depth === 0) break;
      depth -= 1;
    }
    if (character === "," && depth === 0) {
      found.push(current);
      current = "";
      continue;
    }
    current += character;
  }
  if (current.trim() !== "") found.push(current);
  return found;
}

/**
 * Each `<TableCell>…</TableCell>` a `renderCells` prop draws, in source order.
 *
 * The prop is not always one fragment: the declarations tab returns the 수입신고
 * cells or the 생산실적 cells depending on the registry, and its `columns` array
 * branches the same way, in the same order. So every cell after the prop is
 * collected and the caller compares the count with the columns' - a table whose
 * two halves disagree is one this scanner has misread, and it says so rather
 * than measuring the wrong cell against the wrong width.
 */
function jsxCellExpressions(content: string): string[] {
  const start = /renderCells=\{/.exec(content);
  if (start === null) return [];
  const cells: string[] = [];
  const opener = /<TableCell\b/g;
  opener.lastIndex = start.index;
  for (let found = opener.exec(content); found !== null; found = opener.exec(content)) {
    const close = content.indexOf("</TableCell>", found.index);
    if (close === -1) break;
    cells.push(content.slice(found.index, close));
  }
  return cells;
}

/** `const COLUMN … = { field: { floor: N … } }`, by field. */
function columnFloors(content: string): Map<string, number> {
  const floors = new Map<string, number>();
  const table = /const COLUMN[^=]*=\s*\{([\s\S]*?)\n\}/.exec(content);
  if (table === null) return floors;
  for (const match of table[1].matchAll(/([a-z0-9_]+):\s*\{[^}]*floor:\s*([A-Z_0-9]+|\d+)/g)) {
    const raw = match[2];
    const value = /^\d+$/.test(raw) ? Number(raw) : namedNumber(content, raw);
    if (value !== null) floors.set(match[1], value);
  }
  return floors;
}

/** A floor written as an imported constant (`TIMESTAMP_COLUMN_FLOOR`). */
function namedNumber(content: string, name: string): number | null {
  const local = new RegExp(`${name}\\s*=\\s*(\\d+)`).exec(content);
  if (local !== null) return Number(local[1]);
  const config = join(projectRoot, "frontend", "src", "config.ts");
  if (!existsSync(config)) return null;
  const declared = new RegExp(`export const ${name}\\s*=\\s*(\\d+)`).exec(readFileSync(config, "utf-8"));
  return declared === null ? null : Number(declared[1]);
}

interface ColumnDefinition {
  field: string;
  headerKeys: string[];
  /** The locale keys the cell's badge may print; empty when the cell prints none. */
  badgeKeys: string[];
}

/**
 * The vocabulary a badge cell prints, however the screen spells the lookup.
 *
 * Two forms are in use and both are read here, because a check that knew only
 * one would pass the other silently: the key built from the row
 * (`t(\`item_report.kind.${row.report_kind}\`)`) and the key taken from a map
 * beside the column table (`t(KIND_LABEL[row.event_kind])`). A badge printing a
 * row's own text has no vocabulary to measure and is left alone - the column
 * table's floor is the only statement about it.
 */
function badgeKeys(body: string, content: string): string[] {
  if (!body.includes("<Label")) return [];
  const template = /t\(`([^`$]+)\$\{/.exec(body);
  if (template !== null) return [template[1].replace(/\.$/, "")].map((prefix) => `${prefix}.*`);
  const mapped = /t\w*\(\s*([A-Z][A-Z0-9_]*)\[/.exec(body);
  if (mapped !== null) {
    const table = new RegExp(`const ${mapped[1]}[^=]*=\\s*\\{([\\s\\S]*?)\\n\\}`).exec(content);
    if (table !== null) return [...table[1].matchAll(/'([a-z0-9_.]+)'/g)].map((hit) => hit[1]);
  }
  const literal = [...body.matchAll(/<Label[\s\S]*?t\w*\('([^']+)'\)/g)].map((hit) => hit[1]);
  return literal;
}

/** Every `{ ...sized('field'), headerName: t('…'), renderCell … }` in a file. */
function columnDefinitions(content: string): ColumnDefinition[] {
  const found: ColumnDefinition[] = [];
  for (const match of content.matchAll(/\.\.\.sized\('([a-z0-9_]+)'\)/g)) {
    // The definition runs to the next one: a column's `renderCell` is written
    // over several lines and an index of the closing brace read the sibling's.
    const next = content.indexOf("...sized('", match.index + 1);
    const body = content.slice(match.index, next === -1 ? content.length : next);
    const header = [...body.matchAll(/headerName:\s*t\w*\('([^']+)'\)/g)].map((hit) => hit[1]);
    found.push({
      field: match[1],
      headerKeys: header,
      badgeKeys: badgeKeys(body, content),
    });
  }
  return found;
}

/** Every locale value, by key, taking the widest reading of the two locales. */
function localeValues(): Map<string, string> {
  const values = new Map<string, string>();
  for (const file of readdirSync(localesDir)) {
    if (!file.endsWith(".ts")) continue;
    for (const [key, value] of parseLocaleValues(readFileSync(join(localesDir, file), "utf-8"))) {
      // Indexed under the key as written *and* under every tail of it: a screen
      // calls `t('item_report.kind.domestic')` inside its namespace, and the
      // locale file holds `food.item_report.kind.domestic`.
      const parts = key.split(".");
      for (let index = 0; index < parts.length; index += 1) {
        const tail = parts.slice(index).join(".");
        const seen = values.get(tail);
        if (seen === undefined || ink(value, HEADER_INK) > ink(seen, HEADER_INK)) values.set(tail, value);
      }
    }
  }
  return values;
}

/** The keys one level under a prefix - the vocabulary a badge column prints. */
function keysUnder(labels: Map<string, string>, prefix: string): string[] {
  const under: string[] = [];
  for (const key of labels.keys()) {
    if (key.startsWith(`${prefix}.`) && !key.slice(prefix.length + 1).includes(".")) under.push(key);
  }
  return under;
}

/** The widest of several labels, or null when the locale holds none of them. */
function longest(labels: Map<string, string>, keys: string[]): string | null {
  let widest: string | null = null;
  for (const key of keys) {
    const value = labels.get(key);
    if (value === undefined) continue;
    if (widest === null || ink(value, HEADER_INK) > ink(widest, HEADER_INK)) widest = value;
  }
  return widest;
}

/** What a string costs in pixels at one of the measured fonts. */
function ink(text: string, model: { cjk: number; upper: number; lower: number; digit: number; narrow: number }): number {
  let total = 0;
  for (const character of text) {
    const code = character.codePointAt(0) ?? 0;
    if (code > 0x1100) total += model.cjk;
    else if (/[A-Z]/.test(character)) total += model.upper;
    else if (/[a-z]/.test(character)) total += model.lower;
    else if (/[0-9]/.test(character)) total += model.digit;
    else total += model.narrow;
  }
  return total;
}

/** Every `.tsx` under a directory, recursively. */
function sourceFiles(directory: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...sourceFiles(path));
    else if (entry.name.endsWith(".tsx")) files.push(path);
  }
  return files;
}

/**
 * The card a list screen draws into, at the width the product is designed for.
 *
 * Measured in the running app at 1440px: 1,080px of grid inside the card, with
 * the 280px nav and the page's own padding taking the rest. It is a constant
 * here rather than a value read from source because no source states it - the
 * card is `flex: 1` inside a layout, and the number only exists on screen.
 */
const GRID_CARD_WIDTH = 1080;

/**
 * A grid whose rows carry buttons has to fit; a read-only grid may scroll.
 *
 * The floors of the columns that start visible are what the grid asks for, and
 * anything past the card's width goes behind a horizontal scroll. For a list of
 * attributes that is a reader's choice - the 품목 보고 grid asks for 1,690px of
 * nine columns and scrolling it is how a wide registry is read. For a list with
 * an **actions column** it is a defect of a different kind: the buttons are last,
 * so they are what falls off, and a control a reader has to scroll sideways to
 * find is a control they do not know is there. Measured on /batch: seven floors
 * totalling 1,132 against 1,080, and 실행/중지 sat outside the card.
 *
 * The actions column's width is not hand-written anywhere - `rowActionColumnWidth`
 * computes it from the button count - so the same arithmetic is read out of the
 * component rather than copied here, and a change to the button metrics moves
 * this budget with it.
 */
export function checkGridsFitTheirCard(): string[] {
  if (!existsSync(sectionsDir)) return [];
  const issues: string[] = [];
  for (const path of sourceFiles(sectionsDir)) {
    const content = readFileSync(path, "utf-8");
    const floors = columnFloors(content);
    if (floors.size === 0) continue;
    const actions = actionsColumnWidth(content);
    if (actions === null) continue;

    const hidden = hiddenByDefault(content);
    const visible = [...floors].filter(([field]) => !hidden.has(field));
    const columns = visible.reduce((total, [, floor]) => total + floor, 0);
    const total = columns + actions;
    if (total <= GRID_CARD_WIDTH) continue;
    issues.push(
      `src/sections/${relative(sectionsDir, path)}: the columns that start visible floor at ` +
        `${columns}px and the actions column takes ${actions}px, ${total}px against the card's ` +
        `${GRID_CARD_WIDTH}px - the actions are last, so the buttons are what the horizontal ` +
        "scroll hides. Drop a column, start one hidden, or narrow a floor to what it prints",
    );
  }
  return issues;
}

/** `HIDDEN_BY_DEFAULT`'s fields — the columns the selector brings back. */
function hiddenByDefault(content: string): Set<string> {
  const table = /const HIDDEN_BY_DEFAULT[^=]*=\s*\{([\s\S]*?)\n\}/.exec(content);
  if (table === null) return new Set();
  return new Set([...table[1].matchAll(/([a-z0-9_]+):\s*false/g)].map((match) => match[1]));
}

/**
 * What `rowActionsColumn({ count })` reserves, in the component's own arithmetic.
 *
 * Null when the screen renders no actions column: that grid is free to be wider
 * than the card, because nothing but data falls off the end of it.
 */
function actionsColumnWidth(content: string): number | null {
  const code = content.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  const declared = /\browActionsColumn\b[\s\S]{0,600}?\bcount:\s*(\d+)/.exec(code);
  if (declared === null) return null;
  const count = Number(declared[1]);
  const actionsSource = join(projectRoot, "frontend", "src", "components", "data-grid", "RowActions.tsx");
  const gridSource = join(projectRoot, "frontend", "src", "components", "data-grid", "ServerDataGrid.tsx");
  if (!existsSync(actionsSource) || !existsSync(gridSource)) return null;
  const actionsCode = readFileSync(actionsSource, "utf-8");
  const box = namedNumber(actionsCode, "BUTTON_BOX");
  const ink = namedNumber(actionsCode, "BUTTON_INK");
  const gap = namedNumber(actionsCode, "BUTTON_GAP");
  const gutter = cellGutter(readFileSync(gridSource, "utf-8"));
  if (box === null || ink === null || gap === null || gutter === null) return null;
  return count * box + (count - 1) * gap + 2 * (gutter - (box - ink) / 2);
}

/**
 * `CELL_GUTTER_PX = CELL_GUTTER * 8` — the spacing unit, resolved.
 *
 * The unit is read as written and it is **not** an integer: `CELL_GUTTER` is
 * 2.5 (MUI's 8px step, so 20px), and reading it with `\d+` took the 2 and made
 * the actions column 8px narrower than the one on screen.
 */
function cellGutter(content: string): number | null {
  const derived = /CELL_GUTTER_PX\s*=\s*CELL_GUTTER\s*\*\s*(\d+(?:\.\d+)?)/.exec(content);
  const unit = /\bCELL_GUTTER\s*=\s*(\d+(?:\.\d+)?)/.exec(content);
  if (derived === null || unit === null) return null;
  return Number(unit[1]) * Number(derived[1]);
}
