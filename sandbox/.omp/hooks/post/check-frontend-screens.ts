import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import {
  checkGridColumnWidths,
  checkGridDateColumns,
  checkGridsFitTheirCard,
  checkGridHeaderCollisions,
  checkScreenValues,
  checkSectionGaps,
} from "../lib/frontend-grid-width.ts"
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { derivedTablesOf } from "../lib/backend-derivations.ts";
import {
  SRC_DIRECTORIES,
  frontendSrc,
  label,
  projectRoot,
  readIfPresent,
  readSources,
  stripComments,
  walkSources,
} from "../lib/frontend-source.ts";
import {
  checkClippedCellsRevealOnHover,
  checkColumnShares,
  checkRecordDialogStandard,
  checkRecordFieldUsage,
  checkSectionsAnswerWhenEmpty,
} from "../lib/frontend-record-dialog.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { EXECUTION_LOG } from "../lib/hook-product-areas.ts";
import type { ExecutionLog } from "../lib/hook-product-areas.ts";

/**
 * Check-Frontend-Screens Post Hook
 *
 * Validates the per-screen-type templates from .omp/rules/frontend-screens.md.
 * Each screen type has one shape, and the shape is what makes a new screen
 * reviewable against the last one:
 *
 *   list (`<Domain>List.tsx`)       useDataGridState + ServerDataGrid +
 *                                   useCrudDialog, useQueryErrorToast and an
 *                                   empty sentence
 *   form (`<Domain>FormDialog.tsx`) useForm + a resolver + FormProvider, values
 *                                   reset on open, no useState field state
 *   detail (a `detail/` subdirectory) pure presenters — a tab fetches nothing
 *   every section                   reports a failed mutation through useToast
 *                                   and a failed read through useQueryErrorToast
 *
 * `ast-grep/rules/frontend-screen/` owns the structural half (no raw DataGrid).
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/** The one component allowed to render MUI's grid. */
const GRID_OWNER = "frontend/src/components/data-grid/ServerDataGrid.tsx";

/**
 * Hooks a list screen cannot be assembled without.
 *
 * `usePagedRows` was here while the API answered a bare array: the screen had to
 * derive rows and a next-page flag from a peeked extra row. List endpoints now
 * answer `Page<T>`, so the screen reads `items` and `total` straight from the
 * response and the derivation it named has nothing left to do.
 */
/**
 * The pieces a list is assembled from, in the form they take when *used*.
 *
 * Substrings, not word searches: an import satisfies a bare name while the
 * screen draws its own head instead — measured, a planted `<span>` in place of
 * `<ListCardHead` passed a check that looked for the name anywhere in the file.
 * Plain `includes`, because a regex naming the grid would claim an invariant
 * that `ast-grep/rules/frontend-screen/raw-datagrid.yml` already owns.
 */
const LIST_REQUIRED = [
  "useDataGridState(",
  "<ServerDataGrid",
  "useCrudDialog<",
  "<ListCardHead",
  "useListFilters(",
];

export default function checkFrontendScreens(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-screens", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendScreensSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-screens");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-screens",
      issues,
      "run make check-frontend-screens for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-screens") };
  }));
}

export function checkFrontendScreensSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  const scanned = walkSources(frontendSrc).filter((path: string) => label(path) !== GRID_OWNER);
  if (scanned.length > 0) {
    const rulesDir = join(projectRoot, ".omp", "ast-grep", "rules", "frontend-screen");
    issues.push(...runAstRules(rulesDir, scanned));
  }

  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    if (file.label.includes("/detail/")) {
      issues.push(...checkDetailTab(file.label, file.content));
      continue;
    }
    if (file.label.endsWith("List.tsx")) issues.push(...checkListScreen(file.label, file.content));
    if (file.label.endsWith("FormDialog.tsx")) {
      issues.push(...checkFormDialog(file.label, file.content));
    }
    issues.push(...checkMutationFeedback(file.label, file.content));
    issues.push(...checkReadFeedback(file.label, file.content));
    issues.push(...checkDeleteConfirmation(file.label, file.content));
  }

  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    issues.push(...checkRowKeysAreIdentities(file.label, file.content));
  }
  issues.push(...checkPagesAreThin());
  issues.push(...checkListHeadWraps());
  issues.push(...checkFetchDisablesControls());
  issues.push(...checkRowClickGuards());
  issues.push(...checkSelectIsTypedInto());
  issues.push(...checkRecordDialogStandard());
  issues.push(...checkRecordFieldUsage());
  issues.push(...checkClippedCellsRevealOnHover());
  issues.push(...checkColumnShares());
  issues.push(...checkSectionsAnswerWhenEmpty());
  issues.push(...checkGridColumnWidths());
  issues.push(...checkGridsFitTheirCard());
  issues.push(...checkSectionGaps());
  issues.push(...checkScreenValues());
  issues.push(...checkGridDateColumns());
  issues.push(...checkGridHeaderCollisions());

  return issues;
}

/**
 * The pieces a **derived list** is assembled from: the list template with its
 * write half removed. `useCrudDialog` is absent on purpose - the rows are a
 * function of the ledgers, and a dialog here would edit a copy the next
 * rebuild overwrites.
 */
const DERIVED_LIST_REQUIRED = ["useDataGridState(", "<ServerDataGrid", "<ListCardHead", "useListFilters("];

/**
 * What a derived list must not carry: any way to write a row from this side,
 * and no actions column at all - a row nobody edits has one verb, opening its
 * record, and the row itself is that door (`onRowClick` on `ServerDataGrid`).
 */
const DERIVED_LIST_FORBIDDEN = ["useCrudDialog<", "FormDialog", "useToast(", "rowActionsColumn", "processRowUpdate", "useMutation"];

/** The door a derived list's row is. */
const DERIVED_LIST_DOOR = "onRowClick=";

function checkListScreen(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  const derived = fileLabel.endsWith("DerivedList.tsx");
  if (derived) issues.push(...checkDerivedListIsDerived(fileLabel));
  for (const piece of derived ? DERIVED_LIST_REQUIRED : LIST_REQUIRED) {
    if (!content.includes(piece)) {
      const name = piece.replace(/[<(]/g, "");
      issues.push(
        `${fileLabel}: does not use ${name} — a list screen is assembled from the same ` +
          `${LIST_REQUIRED.length} pieces so paging, filtering and dialogs behave identically`,
      );
    }
  }
  if (derived) {
    for (const piece of DERIVED_LIST_FORBIDDEN) {
      if (!content.includes(piece)) continue;
      issues.push(
        `${fileLabel}: a derived list uses ${piece.replace(/[<(]/g, "")} — the rows are a ` +
          "function of the ledgers, rebuilt every night, and a write here is gone by morning",
      );
    }
    if (!content.includes(DERIVED_LIST_DOOR)) {
      issues.push(
        `${fileLabel}: a derived list without onRowClick — the row is the one door into its record, ` +
          "and a grid with no door shows columns the dialog was built to complete",
      );
    }
  }
  if (!/\buseQueryErrorToast\(/.test(content)) {
    issues.push(
      `${fileLabel}: does not call useQueryErrorToast — a failed page renders as an empty ` +
        "list, which is the one state a user cannot tell from success",
    );
  }
  if (!/emptyTitle=/.test(content)) {
    issues.push(`${fileLabel}: passes no emptyTitle — the empty state would have no sentence`);
  }
  issues.push(...checkListHead(fileLabel, content));
  issues.push(...checkFilters(fileLabel, content));
  issues.push(...checkOneControlPerParameter(fileLabel, content));
  issues.push(...checkColumnTable(fileLabel, content));
  issues.push(...checkFilterLabels(fileLabel, content));
  issues.push(...checkServerSort(fileLabel, content));
  issues.push(...checkGridLoading(fileLabel, content));
  if (!derived) {
    issues.push(...checkRowEditRefusal(fileLabel, content));
    issues.push(...checkRowActions(fileLabel, content));
  }
  return issues;
}

/**
 * `*DerivedList.tsx` is a claim about the backend, and the backend has to agree.
 *
 * The suffix relaxes the CRUD template, so it must not be borrowable: a screen
 * earns it only when a derive job rebuilds the table it lists - a `Derivation`
 * of some `backend/app/batch/derive_*.py` whose service is
 * `app/services/<domain>/<table>.py`. Read off the domain folder and the
 * screen's name, so `sections/food/FoodItemReportDerivedList.tsx` is held to
 * the `item_report` derivation and not to "some derived table". A ledger has
 * no screen at all (rule://backend-domain): what a reader sees is the derived
 * table rebuilt off it.
 */
function checkDerivedListIsDerived(fileLabel: string): string[] {
  const domain = fileLabel.split("/").at(-2) ?? "";
  const screen = (fileLabel.split("/").at(-1) ?? "").replace(/DerivedList\.tsx$/, "");
  const table = screen
    .replace(new RegExp(`^${domain.charAt(0).toUpperCase()}${domain.slice(1)}`), "")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .toLowerCase();
  const tables = derivedTablesOf(join(projectRoot, "backend", "app"), domain);
  if (table !== "" && tables.includes(table)) return [];
  return [
    `${fileLabel}: named a derived list, but no derive job rebuilds ${domain}.${table === "" ? "<table>" : table} - ` +
      "no Derivation of backend/app/batch/derive_*.py names its service. A table nothing " +
      "derives is edited by people and gets the CRUD list template (<Domain>List.tsx)",
  ];
}

/**
 * A table row's key is the row's identity, never its words.
 *
 * `rowKey` is what React keeps a row's DOM by. Built from rendered values -
 * `type:item:clause:detail` - it collides the moment the server writes two
 * rows alike, which the Food Code does (가공식품 lists 금속성이물 twice under one
 * heading with the same clause and detail), and a collided key keeps a stale
 * row on every page after the first: measured, nineteen rows on a
 * page of ten. So the expression handed to `rowKey` - inline, or the named
 * function it points at - reads `.id`. A prefix beside the id is fine (a type
 * name before a clause inherited under two types); words instead of it are not.
 */
function checkRowKeysAreIdentities(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  for (const hit of content.matchAll(/rowKey=\{([^}]*)\}/g)) {
    let expression = hit[1].trim();
    const named = /^(\w+)$/.exec(expression);
    if (named !== null) {
      const body = new RegExp(`(?:const|function)\\s+${named[1]}\\b[^\\n]*(?:\\n(?![}\\n])[^\\n]*)*`).exec(content);
      expression = body === null ? "" : body[0];
    }
    if (/\.id\b/.test(expression)) continue;
    issues.push(
      `${fileLabel}: rowKey is not the row's id — a key built from the row's words collides ` +
        "when the server writes two rows alike, and React then keeps a stale row on every page",
    );
  }
  return issues;
}

/**
 * The head is `ListCardHead`, and it carries no density control.
 *
 * Hand-built heads drifted immediately: one screen put the add button alone on a
 * row above the filters, another kept a density control that changed how rows
 * look and nothing about what they are. The frame is one component; only the
 * filter fields are the screen's.
 */
function checkListHead(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  if (/onDensityChange|setDensity/.test(content)) {
    issues.push(
      `${fileLabel}: offers a density control — it changes how the rows look and nothing ` +
        "about what they are, and the row it sat in belongs to the filters",
    );
  }
  if (/<Tabs\b/.test(content)) {
    issues.push(
      `${fileLabel}: builds its own tab strip — the card's head is ListCardHead, so the ` +
        "count badge, the filter row and the two action icons have one definition",
    );
  }
  return issues;
}

/**
 * One box per filterable column, named as the query parameter.
 *
 * `FILTER_FIELDS` is the list of parameter names and the boxes are built from
 * it, so a box, its label and what it sends cannot drift apart. A keyword box
 * over several columns cannot say which column matched.
 */
function checkFilters(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  if (!/const FILTER_FIELDS\s*=\s*\[/.test(content)) {
    issues.push(
      `${fileLabel}: declares no FILTER_FIELDS — the filter boxes are built from the query ` +
        "parameters' own names, or a box sends something the router does not read",
    );
  }
  if (!/<ListFilters\b/.test(content)) {
    issues.push(
      `${fileLabel}: does not render ListFilters — one labelled box per filterable column, ` +
        "never one keyword box that cannot say which column it matched",
    );
  }
  issues.push(...checkSelectFilters(fileLabel, content));
  return issues;
}

/**
 * One query parameter, one control.
 *
 * A list narrows through a single object - the page, the boxes, and whatever the
 * screen adds - so a reader's answer to "why am I seeing these rows" is the set
 * of controls on the screen. When one parameter is driven from two of them, the
 * screen can hold two different answers for one column and neither control shows
 * the other's value.
 *
 * Measured: a tab strip was built over `event_kind` while the same column still
 * had its filter box. Clicking 회수·판매중지 and typing 검사부적합 into the box left
 * a page narrowed by the box, a strip highlighting the other kind, and nothing
 * on screen saying which had won. Every gate was green - the field was in
 * `FILTER_FIELDS`, the parameter reached the repository, the types matched.
 *
 * So the rule is structural, not about tabs: the parameter names a screen writes
 * **literally** into its params object (`event_kind: kind`, or a conditional
 * spread of one) must not also be in `FILTER_FIELDS`, and `FILTER_FIELDS` must
 * not name a column twice. Spreads of `grid.params` / `filters.params` carry no
 * literal key and are not controls of their own.
 */
function checkOneControlPerParameter(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  const declared = [
    ...(/const FILTER_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "").matchAll(/'([a-z0-9_]+)'/g),
  ].map((hit) => hit[1]);

  const seen = new Set<string>();
  for (const field of declared) {
    if (seen.has(field)) {
      issues.push(
        `${fileLabel}: FILTER_FIELDS names ${field} twice — one column, one box`,
      );
    }
    seen.add(field);
  }

  for (const parameter of literalParams(content)) {
    if (!seen.has(parameter)) continue;
    issues.push(
      `${fileLabel}: ${parameter} is set by the screen and by a filter box — one query ` +
        "parameter is driven by one control, or the page is narrowed by a value neither shows",
    );
  }
  return issues;
}

/**
 * The parameter names a screen writes into its own params object.
 *
 * Only the `useMemo<…ListParams>` body is read, and only literal keys in it: a
 * spread (`...filters.params`) is another control's contribution, and guessing
 * at what it contains would report the boxes as a second control over
 * themselves.
 */
function literalParams(content: string): string[] {
  const block = /useMemo<\w*ListParams>\(\s*\(\)\s*=>\s*\(\{([\s\S]*?)\}\),/.exec(content);
  if (block === null) return [];
  const body = block[1].replace(/\.\.\.[\w.]+,?/g, "");
  return [...body.matchAll(/(?:^|[{\s])([a-z][a-z0-9_]*)\s*:/gm)].map((hit) => hit[1]);
}

/**
 * Select filters: options are fetched, the router matches them whole, and a
 * cascade clears its child.
 *
 * Three ways a select can lie, each measured on the raw material ledger before
 * the rule existed:
 * - options typed into the screen offer yesterday's vocabulary the night the
 *   sync brings a new value - so an `options:` fed from an array literal fails;
 * - a select's parameter declared `TextFilterQuery` on the router is matched
 *   by contains, and `식물` returns `식물성유지` - so every `SELECT_FIELDS`
 *   entry must be `ExactFilterQuery` in the domain's router, and every other
 *   `FILTER_FIELDS` entry `TextFilterQuery`;
 * - a cascade whose child is never cleared leaves a filter standing that can
 *   match nothing - so a `CASCADE` declaration owes `setInput(CASCADE.child, '')`;
 * - options that are *codes* (a schema `Literal`, a constant from `types/`)
 *   print as themselves - measured on the report kind: `food` / `livestock` in a
 *   Korean select, with every gate green, because the i18n check reads literal
 *   text and the option was a value. A facets value is the row's own text and
 *   reads as itself; anything else fed to `options:` owes an `optionLabel`.
 */
/**
 * Every filter alias `app/dependencies/query.py` declares, by how the router
 * matches it: a free string with a length floor (`TextFilterQuery`) is a
 * contains-match, and everything else - `ExactFilterQuery`, or an alias whose
 * inner type is a `Literal` the schema closes (`ReportKindQuery`) - matches
 * whole. Read off the declarations, so a new alias is classified by its shape
 * and not by whether this list was updated.
 */
function filterAliasKinds(): Map<string, "text" | "exact"> {
  const kinds = new Map<string, "text" | "exact">();
  const source = readIfPresent(join(projectRoot, "backend", "app", "dependencies", "query.py")) ?? "";
  for (const hit of source.matchAll(/^(\w+Query)\s*=\s*Annotated\[([^\]]+)\]/gm)) {
    const [, alias, inner] = hit;
    if (/\bint\b/.test(inner)) continue; // paging, not a filter
    kinds.set(alias, /\bstr\b/.test(inner) && /min_length/.test(inner) && alias !== "ExactFilterQuery" ? "text" : "exact");
  }
  return kinds;
}

function checkSelectFilters(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  // The expression after `options:` may span a ternary; a quoted string inside
  // square brackets anywhere in its next few lines is a vocabulary typed here.
  const optionsLiteral = [...content.matchAll(/options:((?:[^\n]*\n){0,5})/g)].some((m) => /\[\s*['"]/.test(m[1]));
  if (optionsLiteral) {
    issues.push(
      `${fileLabel}: select options are typed into the screen — a closed vocabulary is the ` +
        "ledger's own distinct values, read from a facets endpoint, or it offers yesterday's choices",
    );
  }
  // The same window as the literal check: a cascade's ternary (text / child / facets) is four lines.
  const optionsFromCodes = [...content.matchAll(/options:((?:[^\n]*\n){0,5})/g)].some(
    (m) => !/\.data\b/.test(m[1]) && !/undefined,?\s*$/.test(m[1].trim()),
  );
  // A select's values come from somewhere: the facets hook that reads the
  // column's own rows, or - for a vocabulary the schema itself closes - the
  // contract's constant, which owes `optionLabel` (checked above). Neither,
  // and the select offers only "all"; measured by planting exactly that on
  // the raw material list, where every gate stayed green.
  const namesFacets = /options:[\s\S]{0,400}?facets\.data/.test(content);
  const readsFacets = /use\w*Facets\(/.test(content);
  const selectNames = [
    ...(/const SELECT_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "").matchAll(/['"]([a-z_]+)['"]/g),
  ].map((m) => m[1]);
  // A column the schema itself closes is named as one (`const CODE_FIELD = 'use_yn'`)
  // and takes its values from the contract; every other select column's values
  // are its own rows', which only the facets read has.
  const codeFields = new RegExp(`const CODE_FIELDS?\\s*=\\s*\\[?([^\\]\\n]*)`).exec(content)?.[1] ?? "";
  const fromRows = selectNames.filter((name) => !codeFields.includes(name));
  if (fromRows.length > 0 && !namesFacets) {
    issues.push(
      `${fileLabel}: select ${fromRows.join(", ")} takes no options from facets.data — a vocabulary ` +
        'the schema does not close is the column\'s own values, or the box offers only "all"',
    );
  }
  if (namesFacets && !readsFacets) {
    issues.push(
      `${fileLabel}: a select reads facets.data but the screen calls no use<Domain><Table>Facets() ` +
        "— the options are undefined on every render",
    );
  }
  if (optionsFromCodes && !/optionLabel:/.test(content)) {
    issues.push(
      `${fileLabel}: select options are codes (not a facets read) and the field carries no ` +
        "optionLabel — a code prints as itself in every language; translate it through the locale",
    );
  }
  const selectBlock = /const SELECT_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "";
  const selects = new Set([...selectBlock.matchAll(/['"]([a-z_]+)['"]/g)].map((m) => m[1]));
  const filterBlock = /const FILTER_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "";
  const filters = [...filterBlock.matchAll(/['"]([a-z_]+)['"]/g)].map((m) => m[1]);
  if (filters.length > 0) {
    const domain = fileLabel.split("/").at(-2) ?? "";
    const routerPath = join(projectRoot, "backend", "app", "routers", `${domain}.py`);
    const router = readIfPresent(routerPath) ?? "";
    const kinds = filterAliasKinds();
    for (const name of filters) {
      const alias = new RegExp(`^\\s+${name}:\\s*(\\w+Query)\\b`, "m").exec(router)?.[1];
      if (alias === undefined || !kinds.has(alias)) {
        // Measured: a planted `ghost_column` in FILTER_FIELDS stayed green under
        // every gate - the box rendered, sent its parameter, and the router
        // ignored it, which is a filter that filters nothing.
        issues.push(
          `${fileLabel}: FILTER_FIELDS names ${name}, which backend/app/routers/${domain}.py ` +
            "accepts as no filter parameter — the box would send something the router ignores",
        );
        continue;
      }
      const wanted = selects.has(name) ? "exact" : "text";
      if (kinds.get(alias) === wanted) continue;
      issues.push(
        `${fileLabel}: ${name} is a ${selects.has(name) ? "select" : "text"} filter here but ` +
          `${alias} on backend/app/routers/${domain}.py — a select's value is picked whole and ` +
          "must match whole; a typed fragment must match by contains",
      );
    }
  }
  if (/const CASCADE\s*=/.test(content) && !/setInput\(CASCADE\.child, ['"]{2}\)/.test(content)) {
    issues.push(
      `${fileLabel}: declares a CASCADE but never clears the child (setInput(CASCADE.child, '')) — ` +
        "a child the new parent does not have would stand as a filter that matches nothing",
    );
  }
  return issues;
}

/**
 * Every list sizes its columns from one table - the 품목제조보고 list's shape.
 *
 * `COLUMN = { field: { floor, share } }` spread by `sized(field)`: the floor is
 * the width at which the widest measured value stops clipping, the share how
 * spare width is divided - across every column, not the two that happened to
 * carry `flex`. A column spelled with its own `width:` or `flex:` is one the
 * table does not know about, and a `width:` literal cannot grow at all: on a
 * 1440px screen the user list's `created_at` sat at 180 and clipped
 * `2026. 8. 30. 오후 10:57` to `10:...` while the flex columns beside it held
 * 321 each. A `*_WIDTH` constant is the same number in a second place.
 *
 * The timestamp floor is one number, because `formatDateTime` writes one
 * string: every `*_at` entry reads `TIMESTAMP_COLUMN_FLOOR` from config.ts
 * (measured 182 at the body size; 185 clears the ink).
 */
function checkColumnTable(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  const code = stripComments(content);
  const table = /const COLUMN\s*:\s*Record<string,\s*\{\s*floor:\s*number;\s*share:\s*number\s*\}>\s*=\s*\{([\s\S]*?)\n\}/.exec(code);
  if (table === null) {
    issues.push(
      `${fileLabel}: declares no COLUMN table — every column's floor and share sit in one ` +
        "`COLUMN = { field: { floor, share } }` spread by sized(field), or a column is sized " +
        "by MUI's 100px default, or by a flex that piles the spare width into itself",
    );
  } else {
    for (const entry of table[1].matchAll(/^\s*(\w+_at):\s*\{\s*floor:\s*([^,]+),/gm)) {
      if (entry[2].trim() === "TIMESTAMP_COLUMN_FLOOR") continue;
      issues.push(
        `${fileLabel}: COLUMN.${entry[1]} has floor ${entry[2].trim()} — a formatted timestamp is ` +
          "one string on every screen, so its floor is TIMESTAMP_COLUMN_FLOOR (config.ts), " +
          "not a number that fit on the day it was typed",
      );
    }
  }
  const widthConstant = /const (\w+_WIDTH)\s*=\s*\d+/.exec(code);
  if (widthConstant !== null) {
    issues.push(
      `${fileLabel}: declares ${widthConstant[1]} — a column's width lives in the COLUMN table ` +
        "beside every other column's, not in a constant the table does not read",
    );
  }
  // ServerDataGrid injects ClippedText into every column without a renderCell;
  // a column that spells it again is the grid's default written a second time.
  if (/renderCell:[^\n]*<ClippedText\b/.test(code)) {
    issues.push(
      `${fileLabel}: a column renders ClippedText itself — ServerDataGrid injects it into every ` +
        "column without a renderCell; a renderCell is for a value that is not text as stored",
    );
  }
  let index = 0;
  while ((index = code.indexOf("field: '", index)) !== -1) {
    const open = code.lastIndexOf("{", index);
    let depth = 0;
    let close = open;
    for (; close < code.length; close += 1) {
      if (code[close] === "{") depth += 1;
      if (code[close] === "}") depth -= 1;
      if (depth === 0) break;
    }
    const object = code.slice(open, close + 1);
    index = close;
    // A column is the object that names its header; `field:` also appears in
    // the argument of a per-cell validator (`showsProblem({ field: 'email' })`).
    if (!/\bheaderName:/.test(object)) continue;
    const field = /field: '([a-z_]+)'/.exec(object)?.[1] ?? "?";
    // The actions column spreads `rowActionsColumn`, which derives its own width
    // from the button count; anything else is a column the table must size.
    if (!/\.\.\.sized\(/.test(object) && !/\.\.\.rowActionsColumn/.test(object)) {
      issues.push(
        `${fileLabel}: column '${field}' is not spread from sized(...) — a column sized on its ` +
          "own line (width, flex, minWidth) is one the COLUMN table does not know about",
      );
    }
  }
  return issues;
}

/**
 * The header's sort is the server's, and the columns it may sort are the
 * router's to close.
 *
 * Measured before the rule: every grid sorted its ten loaded rows on a header
 * click and called it the collection - the model was never wired through, and
 * every gate stayed green. So a list grid carries `sortModel={grid.sortModel}`
 * and `onSortModelChange={grid.setSortModel}` (ServerDataGrid runs
 * `sortingMode="server"`), and every column the grid can sort - one not
 * marked `sortable: false` - is a member of the router's `<Domain>SortQuery`
 * Literal; a header the server refuses would answer 422 on its first click.
 */
function checkServerSort(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  const code = stripComments(content);
  if (!/sortModel=\{grid\.sortModel\}/.test(code) || !/onSortModelChange=\{grid\.setSortModel\}/.test(code)) {
    issues.push(
      `${fileLabel}: the grid is not wired to grid.sortModel / grid.setSortModel — a header ` +
        "click would sort the loaded page and call it the collection",
    );
  }
  const domain = fileLabel.split("/").at(-2) ?? "";
  const router = readIfPresent(join(projectRoot, "backend", "app", "routers", `${domain}.py`)) ?? "";
  const query = readIfPresent(join(projectRoot, "backend", "app", "dependencies", "query.py")) ?? "";
  // The list endpoint this screen pages: the one whose service call the screen's
  // list hook names is not visible here, so take the router's top-level Page
  // endpoints and the SortQuery each declares; a domain with two (food) is told
  // apart by the alias name carrying the screen's table.
  const aliases = [...router.matchAll(/sort:\s*(\w+SortQuery)\s*=/g)].map((m) => m[1]);
  const table = /sections\/\w+\/(\w+?)(?:Derived)?List\.tsx$/.exec(fileLabel)?.[1] ?? "";
  const alias = aliases.find((name) => name === `${table}SortQuery`) ?? aliases[0];
  if (alias === undefined) return issues;
  const start = query.indexOf(`${alias} = Annotated[`);
  if (start === -1) return issues;
  const literal = /Literal\[([\s\S]*?)\]\s*\|\s*None/.exec(query.slice(start))?.[1] ?? "";
  const sortable = new Set([...literal.matchAll(/"(\w+)"/g)].map((m) => m[1]));
  let index = 0;
  while ((index = code.indexOf("...sized('", index)) !== -1) {
    const open = code.lastIndexOf("{", index);
    let depth = 0;
    let close = open;
    for (; close < code.length; close += 1) {
      if (code[close] === "{") depth += 1;
      if (code[close] === "}") depth -= 1;
      if (depth === 0) break;
    }
    const object = code.slice(open, close + 1);
    index = close;
    const field = /\.\.\.sized\('(\w+)'\)/.exec(object)?.[1] ?? "";
    if (sortable.has(field) || /sortable:\s*false/.test(object)) continue;
    issues.push(
      `${fileLabel}: column '${field}' is sortable but ${alias} on backend/app/dependencies/query.py ` +
        "does not name it — the first click of that header answers 422; add it to the Literal " +
        "or say sortable: false",
    );
  }
  return issues;
}

/**
 * Filter labels are looked up, never branched.
 *
 * `FILTER_LABEL_KEYS` maps every `FILTER_FIELDS` entry to its locale key and the
 * box reads `t(FILTER_LABEL_KEYS[field])`. A ternary on the field name is right
 * for two fields and silently wrong for the third: the else branch labels
 * whatever is added next (`field === 'code' ? t('filter.code') : t('filter.display_name')`
 * would call a new `base_url` box 표시명).
 */
function checkFilterLabels(fileLabel: string, content: string): string[] {
  const code = stripComments(content);
  const filterBlock = /const FILTER_FIELDS\s*=\s*\[([^\]]*)\]/.exec(code)?.[1];
  if (filterBlock === undefined) return [];
  const fields = [...filterBlock.matchAll(/['"]([a-z_]+)['"]/g)].map((m) => m[1]);
  const keys = /const FILTER_LABEL_KEYS\s*=\s*\{([\s\S]*?)\}\s*as const/.exec(code)?.[1];
  if (keys === undefined) {
    return [
      `${fileLabel}: declares no FILTER_LABEL_KEYS — a box's label is looked up by its field ` +
        "(t(FILTER_LABEL_KEYS[field])), never chosen by a ternary on the field's name",
    ];
  }
  const issues: string[] = [];
  const named = new Set([...keys.matchAll(/^\s*(\w+):/gm)].map((m) => m[1]));
  for (const field of fields) {
    if (named.has(field)) continue;
    issues.push(`${fileLabel}: FILTER_LABEL_KEYS has no key for ${field} — every FILTER_FIELDS entry owes its label key`);
  }
  if (!/label:\s*t\(FILTER_LABEL_KEYS\[field\]\)/.test(code)) {
    issues.push(
      `${fileLabel}: the filter box label is not t(FILTER_LABEL_KEYS[field]) — the label is the map's ` +
        "answer for the field, not a branch on its name",
    );
  }
  return issues;
}

/**
 * A select filter is typed into, not only scrolled.
 *
 * The vocabularies are the columns' own values and some are long: 814 식품유형
 * on the item report list, 85 상태 on the raw material one (measured
 * live). A plain `TextField select` makes the reader hunt a value they
 * already know through a list that height, so `ListFilters` renders an
 * `Autocomplete` whose typing narrows by contains - and what it sends is still
 * one of the options, so the router's equals holds.
 */
function checkSelectIsTypedInto(): string[] {
  // existence-ok: every list screen imports it; a missing one fails the build first.
  const source = readIfPresent(join(frontendSrc, "components", "data-grid", "ListFilters.tsx"));
  if (source === null) return [];
  const code = stripComments(source);
  if (/<Autocomplete\b/.test(code) && !/<TextField\b[^>]*\bselect\b/.test(code)) return [];
  return [
    "frontend/src/components/data-grid/ListFilters.tsx: a select filter is a plain dropdown — " +
      "render Autocomplete, whose typing narrows a vocabulary the reader cannot scroll " +
      "(measured: 814 식품유형, 85 상태)",
  ];
}

/**
 * The grid's progress reads the fetch, not the mount.
 *
 * Every list keeps the previous page on screen while the next one loads
 * (`placeholderData: (previous) => previous`), so `query.isLoading` is `true`
 * only once, on the very first mount - a filter box, a header sort or a page
 * click all set `isFetching` without ever setting `isLoading` again.
 * `loading={query.isLoading}` showed rows aging silently on a slow connection
 * with no sign a request was in flight (measured: 700ms latency, six checks
 * 150ms apart, no overlay). `loading={query.isFetching}` costs nothing new -
 * MUI's own `GridLoadingOverlay` draws a `linear-progress` bar over the
 * existing rows whenever `loading` is `true` and the grid already has rows.
 */
function checkGridLoading(fileLabel: string, content: string): string[] {
  const code = stripComments(content);
  if (!code.includes("<ServerDataGrid")) return [];
  const issues: string[] = [];
  if (/loading=\{query\.isLoading\}/.test(code)) {
    issues.push(
      `${fileLabel}: ServerDataGrid reads loading={query.isLoading} — a refetch after the ` +
        "first mount (a filter, a sort, a page) never sets isLoading again, so the grid shows " +
        "no progress while the rows it displays go stale; use query.isFetching",
    );
  } else if (!/loading=\{query\.isFetching\}/.test(code)) {
    issues.push(
      `${fileLabel}: ServerDataGrid's loading prop is not query.isFetching — a query in flight ` +
        "must show the grid's own progress bar, not silence while rows age on screen",
    );
  }
  if (/<ListFilters\b[\s\S]*?disabled=/.test(code)) {
    issues.push(
      `${fileLabel}: ListFilters carries a disabled prop — a box that locks while the fetch ` +
        "runs cuts the word still being typed (measured: 밀가 sent, 루 dropped); the query key " +
        "closes the race, not the box",
    );
  }
  return issues;
}

/**
 * A page in flight is not the only request a second click can start. Two
 * requests for the same screen racing land in either order, and the one that
 * lands second silently wins the footer's total and the rows shown - even if
 * it answers an older filter or an earlier page. `loading` already names that
 * window, so `ServerDataGrid` - the one file every list renders, not each
 * caller - disables everything inside it that would start a second request:
 * its own paging and its own sorting.
 */
function checkFetchDisablesControls(): string[] {
  const issues: string[] = [];
  // existence-ok: every dialog table imports this file; a missing one fails the build first.
  const table = readIfPresent(join(frontendSrc, "components", "detail", "ServerPagedTable.tsx"));
  if (table !== null) {
    const tableCode = stripComments(table);
    if (!/<TablePagination\b[^>]*disabled=\{loading\}/.test(tableCode) || !/<LinearProgress\b/.test(tableCode)) {
      issues.push(
        "frontend/src/components/detail/ServerPagedTable.tsx: does not draw LinearProgress and lock " +
          "TablePagination from its loading prop — a dialog's table is the same contract as the " +
          "grid (measured: the runs dialog paged with live buttons and no bar)",
      );
    }
  }
  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    const sectionCode = stripComments(file.content);
    // The props before renderCells: the cells' own JSX closes tags of its own.
    for (const call of sectionCode.matchAll(/<ServerPagedTable\b([\s\S]*?)(?:renderCells=|\/>)/g)) {
      if (/loading=\{(?:\w+\.)?(?:isFetching|loading)\}/.test(call[1])) continue;
      issues.push(
        `${file.label}: ServerPagedTable without loading={<query>.isFetching} — the dialog's page ` +
          "in flight shows no bar and its footer stays live for a second, racing request",
      );
    }
  }
  // existence-ok: every list screen imports this file; a missing one fails the build first.
  const grid = readIfPresent(join(frontendSrc, "components", "data-grid", "ServerDataGrid.tsx"));
  if (grid === null) return issues;
  const code = stripComments(grid);
  if (!/slotProps=\{\{\s*basePagination:\s*\{\s*disabled:\s*loading\s*\}\s*\}\}/.test(code)) {
    issues.push(
      "frontend/src/components/data-grid/ServerDataGrid.tsx: no slotProps={{ basePagination: " +
        "{ disabled: loading } }} — a page click while the last page is still in flight races " +
        "the two responses for the rows shown (pagination is the wrong slot key; GridPagination " +
        "reads basePagination)",
    );
  }
  if (!/disableColumnSorting=\{loading\}/.test(code)) {
    issues.push(
      "frontend/src/components/data-grid/ServerDataGrid.tsx: no disableColumnSorting={loading} " +
        "— a header click while a page is in flight races the two responses the same way a " +
        "second page click does",
    );
  }
  return issues;
}

/**
 * The head's filter boxes never leave the row: six boxes at 1400px put the last
 * select off-screen (x=1530). Either mechanism holds it - a wrapping flex row,
 * or a grid that fits as many `minmax(..., 1fr)` cells as the row holds and
 * folds the rest (the second also fills the row, which the first left ragged
 * at 900px). The property is checked, not the spelling.
 */
function checkListHeadWraps(): string[] {
  // existence-ok: every list screen imports the head, and checkListHead reports one that is missing
  const source = readIfPresent(join(frontendSrc, "components", "data-grid", "ListCardHead.tsx"));
  if (source === null || /flexWrap="wrap"/.test(source) || /repeat\(auto-fit,\s*minmax\(/.test(source)) {
    return [];
  }
  return [
    "frontend/src/components/data-grid/ListCardHead.tsx: the filter row does not wrap — " +
      "a screen with more boxes than the row holds pushes a filter off-screen, where it does not exist",
  ];
}

/**
 * A grid that edits refuses out loud.
 *
 * MUI answers an invalid row by staying open and saying nothing, so the save
 * button reads as broken. A screen that edits in the grid holds `apiRef`, judges
 * the pending values with the same function its cells use, and names the field.
 */
function checkRowEditRefusal(fileLabel: string, content: string): string[] {
  if (!/processRowUpdate/.test(content)) return [];
  const issues: string[] = [];
  // Both halves: a screen that holds the ref but never hands it to the grid reads
  // the edit state of nothing (measured — a planted `{ current: null }` passed a
  // check that only looked for the word).
  if (!/useGridApiRef\(/.test(content) || !/apiRef=\{/.test(content)) {
    issues.push(
      `${fileLabel}: edits rows without the grid's apiRef — the pending values live in the ` +
        "grid's edit state, so a blocked save can only be watched, never explained",
    );
  }
  // `problemOf` is **called** twice: from the cells' `preProcessEditCellProps` and
  // from `refusal`. A screen that reds a cell by one rule and refuses the save by
  // another is the disagreement this pair exists to prevent. The declaration is
  // subtracted — counting it passed a planted screen whose cells judged nothing.
  const problemOfCalls =
    (content.match(/\bproblemOf\(/g) ?? []).length - (content.match(/function problemOf\(/g) ?? []).length;
  if (problemOfCalls < 2) {
    issues.push(
      `${fileLabel}: judges its cells and its save by different rules — the red cell and the ` +
        "sentence a blocked save shows both come from problemOf, or they disagree",
    );
  }
  // The flow around that judgement is `useRowEditor`'s: the modes map, the three
  // commands, the deferred focus and the `reported` flag were 24 identical lines
  // in two screens before it existed, and a screen that reimplements them drifts
  // from the one the exemplar proves.
  if (!/useRowEditor</.test(content) || !/refusal[,\s]/.test(content)) {
    issues.push(
      `${fileLabel}: edits rows without handing a refusal to useRowEditor — the commit, the ` +
        "caret move and the one-sentence report belong to that hook, not to each screen",
    );
  }
  return issues;
}

/**
 * Row actions come from `rowActionsColumn`, never from a hand-written cell.
 *
 * A hand-rolled `renderCell` for actions is how the column drifted twice: it was
 * sized 96px for two buttons and then given a third, and its buttons sat outside
 * the grid's focus and `tabIndex` handling. `rowActionsColumn` returns MUI's own
 * `type: 'actions'` column, so width, alignment and focus have one owner.
 */
function checkRowActions(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  if (/field:\s*['"`]actions['"`]/.test(content)) {
    issues.push(
      `${fileLabel}: hand-written actions column — call rowActionsColumn, which ` +
        "returns MUI's type: 'actions' column with the width computed from the buttons",
    );
  }
  issues.push(...checkActionCountBudget(fileLabel, content));
  return issues;
}

/**
 * A row that is both a door and an editor guards the click centrally.
 *
 * The blanket ban read "a row that opens a record cannot also be a row a user
 * types into", and as a screen-level rule it was the wrong owner: the collision
 * is in the grid, and it is two collisions, not one. A click inside the actions
 * cell is reported as a row click as well, so a door would open a dialog on the
 * way to `삭제`; and MUI opens an editor on cell double-click, whose first click
 * had already opened that dialog. Both are fixed once, in `ServerDataGrid`, so
 * every screen that carries a door inherits the same answer.
 *
 * Checked on the owner, because that is where the guard lives: a screen passing
 * `onRowClick` is no longer a violation, and a grid owner missing a guard is.
 */
function checkRowClickGuards(): string[] {
  const issues: string[] = [];
  // existence-ok: every list screen imports this file; a missing one fails the build first.
  const grid = readIfPresent(join(frontendSrc, "components", "data-grid", "ServerDataGrid.tsx"));
  if (grid === null) return issues;
  const code = stripComments(grid);
  if (!/rowModesModel\?\.\[params\.id\]\?\.mode\s*===\s*GridRowModes\.Edit/.test(code)) {
    issues.push(
      `${GRID_OWNER}: a row click is not gated on the row's edit mode — a row being typed ` +
        "into answers the pointer with a dialog over the cell it was aiming at",
    );
  }
  if (!/closest\(\s*'\[data-field="actions"\]'\s*\)/.test(code)) {
    issues.push(
      `${GRID_OWNER}: a row click is not gated on the actions cell — MUI reports one for a ` +
        "click on a row button too, so the door opens on the way to delete",
    );
  }
  if (!/onCellDoubleClick=\{[\s\S]{0,200}?defaultMuiPrevented\s*=\s*true/.test(code)) {
    issues.push(
      `${GRID_OWNER}: cell double-click still starts an editor while a door is set — the ` +
        "first of the two clicks opened the dialog, so the second lands on a grid behind it",
    );
  }
  return issues;
}

/**
 * `count` reserves the column's width, and it is the **widest** branch's length.
 *
 * `rowActionColumnWidth(count)` is what the column asks the grid for, so a
 * `count` below what a row can render sizes the column for fewer buttons than it
 * draws and the last ones are clipped — reachable by nothing, reported by
 * nothing. Types cannot catch it (`count` is a number and the array is built at
 * runtime) and neither can a test that never measures the column.
 *
 * It is a **maximum**, not an equality with one array: a row that edits in place
 * returns save/cancel while editing and view/edit/delete otherwise, so the
 * exemplar declares 3 while one of its branches has 2. An equality check was
 * written first and fired on that screen — the standard is the width the widest
 * row needs, because that is the width the column keeps in every row.
 *
 * Branches that measure zero are dropped rather than compared: an index
 * expression (`rowModes[id]`) opens a bracket that is not an array literal, and a
 * call the scanner cannot read must not become a violation nobody can act on.
 */
function checkActionCountBudget(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  for (const call of rowActionsCalls(stripComments(content))) {
    const declared = /\bcount:\s*(\d+)/.exec(call);
    if (declared === null) continue;
    const branches = actionBranchLengths(call).filter((size: number) => size > 0);
    if (branches.length === 0) continue;
    const widest = Math.max(...branches);
    const reserved = Number(declared[1]);
    if (reserved === widest) continue;
    const consequence =
      reserved < widest
        ? "the column is sized for fewer buttons than a row draws, so the last ones " +
          "are clipped and cannot be clicked"
        : "the column reserves width no row fills, and that width comes off the " +
          "data columns beside it";
    issues.push(
      `${fileLabel}: rowActionsColumn declares count: ${reserved} but its widest ` +
        `branch renders ${widest} action(s) — ${consequence}`,
    );
  }
  return issues;
}

/** Each `rowActionsColumn(...)` argument list, generic parameters skipped. */
function rowActionsCalls(code: string): string[] {
  const calls: string[] = [];
  const marker = /\browActionsColumn\b/g;
  for (let found = marker.exec(code); found !== null; found = marker.exec(code)) {
    const open = code.indexOf("(", found.index);
    if (open === -1) continue;
    const body = balancedSlice(code, open);
    if (body !== null) calls.push(body);
  }
  return calls;
}

/** From an opening `(` to its match, string-aware. */
function balancedSlice(code: string, open: number): string | null {
  let depth = 0;
  let quote = "";
  for (let index = open; index < code.length; index += 1) {
    const char = code[index];
    if (quote !== "") {
      if (char === "\\") index += 1;
      else if (char === quote) quote = "";
      continue;
    }
    if (char === "'" || char === '"' || char === "`") quote = char;
    else if (char === "(") depth += 1;
    else if (char === ")") {
      depth -= 1;
      if (depth === 0) return code.slice(open, index + 1);
    }
  }
  return null;
}

/**
 * How many objects each array literal under `actions:` holds.
 *
 * One number per branch: a plain arrow returns one array, a ternary two. Objects
 * are counted only at the array's own element depth, so the props inside an
 * action never inflate its neighbour's total.
 */
function actionBranchLengths(call: string): number[] {
  const start = call.search(/\bactions\s*:/);
  if (start === -1) return [];
  const region = call.slice(start);
  const lengths: number[] = [];
  let depth = 0;
  let arrayDepth = -1;
  let objects = 0;
  // `...historyActions(row)` holds elements the scanner cannot count, so the
  // branch is unmeasurable, not short — counting only the literals fired
  // "count too high" on a legitimate extraction of three actions into a helper.
  let spread = false;
  let quote = "";
  for (let index = 0; index < region.length; index += 1) {
    const char = region[index];
    if (quote !== "") {
      if (char === "\\") index += 1;
      else if (char === quote) quote = "";
      continue;
    }
    if (char === "'" || char === '"' || char === "`") {
      quote = char;
    } else if (char === "[") {
      if (arrayDepth === -1) {
        arrayDepth = depth;
        objects = 0;
        spread = false;
      }
      depth += 1;
    } else if (char === "]") {
      depth -= 1;
      if (depth === arrayDepth) {
        if (!spread) lengths.push(objects);
        arrayDepth = -1;
      }
    } else if (char === "." && arrayDepth !== -1 && depth === arrayDepth + 1) {
      spread = true;
    } else if (char === "{") {
      if (arrayDepth !== -1 && depth === arrayDepth + 1) objects += 1;
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
    } else if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth -= 1;
      if (depth < 0) break;
    }
  }
  return lengths;
}

function checkFormDialog(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  if (!/\buseForm\b/.test(content) || !/Resolver\(/.test(content)) {
    issues.push(
      `${fileLabel}: no useForm with a resolver — validation belongs to the schema, ` +
        "not to a hand-written check before submit",
    );
  }
  if (!/<FormProvider\b/.test(content)) {
    issues.push(`${fileLabel}: does not render FormProvider — Enter would not submit the form`);
  }
  if (!/methods\.reset\(/.test(content)) {
    issues.push(
      `${fileLabel}: never calls methods.reset — the dialog stays mounted, so the ` +
        "second row edited would show the first row's values",
    );
  }
  if (/\buseState[<(]/.test(content)) {
    issues.push(
      `${fileLabel}: holds field state in useState — the resolver then validates a ` +
        "different value than the user sees",
    );
  }
  return issues;
}

/**
 * A tab that fetches refetches on every tab switch and can disagree with its
 * siblings — **unless what it reads is not part of the entity at all.**
 *
 * An execution log is exactly that case: it is unbounded (a row per call, for
 * ever), server-paged, and written by whatever exercised the configuration, so
 * it cannot be nested in the entity read the other tabs share. There is no
 * second version of those rows to disagree with. The allowance is narrow: the
 * only query hooks such a tab may call are the ones `EXECUTION_LOG` declares
 * (rule://product-areas), so a tab re-reading its own entity still fails.
 */
function checkDetailTab(fileLabel: string, content: string): string[] {
  const imported = [...content.matchAll(/import\s+\{([^}]+)\}\s+from\s+['"]@\/lib\/api\/hooks\/[^'"]+['"]/g)]
    .flatMap((match: RegExpMatchArray) => match[1].split(",").map((name: string) => name.trim()));
  if (imported.length === 0) return [];
  const logHooks = Object.values(EXECUTION_LOG).map((log: ExecutionLog) => log.hook);
  if (imported.every((hook: string) => logHooks.includes(hook))) return [];
  return [
    `${fileLabel}: a detail tab queries its own data — take the entity as a prop ` +
      "so every tab shows one version of the row (an execution log declared in " +
      "EXECUTION_LOG is the one collection a tab may read for itself)",
  ];
}

function checkMutationFeedback(fileLabel: string, content: string): string[] {
  // Three ways to report, all of them naming the failure: the shared mapper,
  // a toast, or the mapped sentence rendered where the result would go — which
  // is what a console does, because the failure *is* the result of the call.
  const reports =
    /toast\.error\(/.test(content) ||
    /applyServerError\(/.test(content) ||
    /serverErrorMessage\(/.test(content);
  if (/mutateAsync\(/.test(content) && !reports) {
    return [
      `${fileLabel}: awaits a mutation without reporting failure — map the server code through ` +
        "applyServerError / serverErrorMessage (or useToast), or a rejected write looks like a " +
        "successful one",
    ];
  }
  return [];
}

/**
 * A failed read speaks as a toast, never as a banner in the body.
 *
 * Reads and writes used to fail in two vocabularies on one screen: an inline
 * `<Alert>` above the table for a failed page, a toast for a rejected save. The
 * banner also carried the only retry, duplicating the toolbar's refresh, and in
 * a dialog it replaced the table it was describing. `useQueryErrorToast` is the
 * one way in; the toolbar refresh is the one retry.
 */
function checkReadFeedback(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  for (const line of content.split("\n")) {
    if (!line.includes("messages.load_failed")) continue;
    if (/useQueryErrorToast\(/.test(line)) continue;
    issues.push(
      `${fileLabel}: renders messages.load_failed in the body — a failed read is reported ` +
        "by useQueryErrorToast, so reads and writes fail in one vocabulary",
    );
  }
  if (/\{[^{}]*\.isError\s*(\?|&&)/.test(content)) {
    issues.push(
      `${fileLabel}: branches on isError inside JSX — the failed read is a toast, and the ` +
        "retry is the toolbar's refresh; a body branch is the banner coming back",
    );
  }
  return issues;
}

/**
 * The delete question is one sentence, and the domain writes it.
 *
 * Every caller used to append "이 작업은 되돌릴 수 없습니다" behind a `<br />`,
 * which made a rule of the API a second sentence of the same weight as the fact
 * about the row. `messages.delete_confirm` names the row *and* what deleting it
 * costs; the dialog's title says the verb once.
 */
function checkDeleteConfirmation(fileLabel: string, content: string): string[] {
  const opened = content.indexOf("<ConfirmDialog");
  if (opened === -1) return [];
  // To the element's own closing tag, not to the first `/>`: a `<br />` inside
  // the question ended the slice before the very text this check is about.
  const closed = content.indexOf("\n      />", opened);
  const block = content.slice(opened, closed === -1 ? content.length : closed);
  const issues: string[] = [];
  if (/cannot_undo/.test(block)) {
    issues.push(
      `${fileLabel}: passes cannot_undo into ConfirmDialog — the domain's own sentence says ` +
        "what deleting costs, in one sentence with the row it costs",
    );
  }
  if (/<br\s*\/?>/.test(block)) {
    issues.push(
      `${fileLabel}: builds the delete question from two lines — one sentence, or the reader ` +
        "reads a rule of the API as a fact about this row",
    );
  }
  if (!/title=/.test(block)) {
    issues.push(
      `${fileLabel}: opens ConfirmDialog without a title — the head names the verb once so ` +
        "the body never repeats it",
    );
  }
  return issues;
}

/**
 * A page is a header plus one section: fetching there splits a screen in two.
 *
 * Only the pages routed inside `DashboardLayout` need a `PageHeader` — login
 * and the catch-all render outside the shell, where there is no breadcrumb
 * trail to show. The set is read from the route table rather than listed here,
 * so moving a page under the layout starts requiring its header.
 */
function checkPagesAreThin(): string[] {
  const issues: string[] = [];
  const inShell = dashboardPages();
  for (const file of readSources(SRC_DIRECTORIES.pages)) {
    if (/from ['"]@\/lib\/api\/hooks\//.test(file.content)) {
      issues.push(
        `${file.label}: a page queries data — move it into the section it renders, so a ` +
          "route change never has to move a query",
      );
    }
    const component = (file.label.split("/").pop() ?? "").replace(/\.tsx$/, "");
    if (inShell.has(component) && !/<PageHeader\b/.test(file.content)) {
      issues.push(`${file.label}: renders no PageHeader — the screen has no heading or breadcrumb`);
    }
  }
  return issues;
}

/** The page components routed under `DashboardLayout` in the route table. */
function dashboardPages(): Set<string> {
  // existence-ok: App.tsx is a required entry file — check-frontend-code reports its absence.
  const source = readIfPresent(join(frontendSrc, "App.tsx"));
  if (source === null) return new Set();
  const start = source.indexOf("<DashboardLayout />");
  if (start === -1) return new Set();
  const block = source.slice(start, source.indexOf("</Route>", start));
  return new Set(
    [...block.matchAll(/element=\{<(\w+)\s*\/>\}/g)].map((match: RegExpMatchArray) => match[1]),
  );
}

// Direct execution (make check-frontend-screens): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-screens.ts")) {
  const issues = checkFrontendScreensSync();
  console.log("==> check-frontend-screens");
  if (issues.length === 0) {
    console.log("    PASS: every screen follows its type's template");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-screens");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
