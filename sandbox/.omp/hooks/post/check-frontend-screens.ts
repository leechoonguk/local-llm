import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { ledgerTablesOf } from "../lib/backend-ledger-feeds.ts";
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
} from "../lib/frontend-record-dialog.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

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

  issues.push(...checkPagesAreThin());
  issues.push(...checkListHeadWraps());
  issues.push(...checkRecordDialogStandard());
  issues.push(...checkRecordFieldUsage());
  issues.push(...checkClippedCellsRevealOnHover());
  issues.push(...checkColumnShares());
  return issues;
}

/**
 * The pieces a **ledger list** is assembled from: the list template with its
 * write half removed. `useCrudDialog` is absent on purpose - the rows belong to
 * a nightly sync, and a dialog here would edit a copy the next pass overwrites.
 */
const LEDGER_LIST_REQUIRED = ["useDataGridState(", "<ServerDataGrid", "<ListCardHead", "useListFilters("];

/** What a ledger list must not carry: any way to write a row from this side. */
const LEDGER_LIST_FORBIDDEN = ["useCrudDialog<", "FormDialog", "useToast(", "rowActionsColumn", "processRowUpdate", "useMutation"];

function checkListScreen(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  const ledger = fileLabel.endsWith("LedgerList.tsx");
  if (ledger) issues.push(...checkLedgerListIsALedger(fileLabel));
  for (const piece of ledger ? LEDGER_LIST_REQUIRED : LIST_REQUIRED) {
    if (!content.includes(piece)) {
      const name = piece.replace(/[<(]/g, "");
      issues.push(
        `${fileLabel}: does not use ${name} — a list screen is assembled from the same ` +
          `${LIST_REQUIRED.length} pieces so paging, filtering and dialogs behave identically`,
      );
    }
  }
  if (ledger) {
    for (const piece of LEDGER_LIST_FORBIDDEN) {
      if (!content.includes(piece)) continue;
      issues.push(
        `${fileLabel}: a ledger list uses ${piece.replace(/[<(]/g, "")} — the rows are a ` +
          "nightly sync's copy of the provider's, and a write here is overwritten by morning",
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
  issues.push(...checkColumnSizing(fileLabel, content));
  if (!ledger) {
    issues.push(...checkRowEditRefusal(fileLabel, content));
    issues.push(...checkRowActions(fileLabel, content));
  }
  return issues;
}

/**
 * `*LedgerList.tsx` is a claim about the backend, and the backend has to agree.
 *
 * The suffix relaxes the CRUD template, so it must not be borrowable: a screen
 * earns it only when a provider job replaces the table it lists - a `Feed` of
 * some `backend/app/batch/sync_<provider>_ledgers.py` whose service is
 * `app/services/<domain>/<table>.py`. Read off the domain folder and the
 * screen's name, so `sections/food/FoodRawMaterialLedgerList.tsx` is held to
 * the `raw_material` feed and not to "some ledger".
 */
function checkLedgerListIsALedger(fileLabel: string): string[] {
  const domain = fileLabel.split("/").at(-2) ?? "";
  const screen = (fileLabel.split("/").at(-1) ?? "").replace(/LedgerList\.tsx$/, "");
  const table = screen
    .replace(new RegExp(`^${domain.charAt(0).toUpperCase()}${domain.slice(1)}`), "")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .toLowerCase();
  const tables = ledgerTablesOf(join(projectRoot, "backend", "app"), domain);
  if (table !== "" && tables.includes(table)) return [];
  return [
    `${fileLabel}: named a ledger list, but no provider job replaces ${domain}.${table === "" ? "<table>" : table} - ` +
      "no Feed of backend/app/batch/sync_*_ledgers.py names its service. A table nothing " +
      "syncs is edited by people and gets the CRUD list template (<Domain>List.tsx)",
  ];
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
 *   match nothing - so a `CASCADE` declaration owes `setInput(CASCADE.child, '')`.
 */
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
  const selectBlock = /const SELECT_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "";
  const selects = new Set([...selectBlock.matchAll(/['"]([a-z_]+)['"]/g)].map((m) => m[1]));
  const filterBlock = /const FILTER_FIELDS\s*=\s*\[([^\]]*)\]/.exec(content)?.[1] ?? "";
  const filters = [...filterBlock.matchAll(/['"]([a-z_]+)['"]/g)].map((m) => m[1]);
  if (filters.length > 0) {
    const domain = fileLabel.split("/").at(-2) ?? "";
    const routerPath = join(projectRoot, "backend", "app", "routers", `${domain}.py`);
    const router = readIfPresent(routerPath) ?? "";
    for (const name of filters) {
      const alias = new RegExp(`^\\s+${name}:\\s*(TextFilterQuery|ExactFilterQuery)\\b`, "m").exec(router)?.[1];
      if (alias === undefined) {
        // Measured: a planted `ghost_column` in FILTER_FIELDS stayed green under
        // every gate - the box rendered, sent its parameter, and the router
        // ignored it, which is a filter that filters nothing.
        issues.push(
          `${fileLabel}: FILTER_FIELDS names ${name}, which backend/app/routers/${domain}.py ` +
            "accepts as no filter parameter — the box would send something the router ignores",
        );
        continue;
      }
      const wanted = selects.has(name) ? "ExactFilterQuery" : "TextFilterQuery";
      if (alias === wanted) continue;
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
 * Every grid column has a floor and, if it may grow, a share.
 *
 * MUI's default is 100px with no floor, which clipped the 14-character codes
 * and `식품원료(A코드)` on the raw material ledger; and `flex` on two columns
 * alone piled a 1920px screen's spare width into those two while the rest
 * stayed clipped. So a column literal carries `width`, or `flex` with
 * `minWidth`; a `...sized(...)` spread is exempt, because it is built from a
 * table whose type already requires both.
 */
function checkColumnSizing(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  let index = 0;
  while ((index = content.indexOf("field: '", index)) !== -1) {
    const open = content.lastIndexOf("{", index);
    const before = content.slice(open, index);
    if (before.includes("...sized(")) {
      index += 1;
      continue;
    }
    // Walk to the matching brace of the object the field sits in.
    let depth = 0;
    let close = open;
    for (; close < content.length; close += 1) {
      if (content[close] === "{") depth += 1;
      if (content[close] === "}") depth -= 1;
      if (depth === 0) break;
    }
    const object = content.slice(open, close + 1);
    const field = /field: '([a-z_]+)'/.exec(object)?.[1] ?? "?";
    const sized = /\bwidth:/.test(object) || (/\bflex:/.test(object) && /\bminWidth:/.test(object));
    // A spread anywhere in the object (`...rowActionsColumn`, `...sized`) sizes itself.
    if (!sized && !/\.\.\.\w+\(/.test(object)) {
      issues.push(
        `${fileLabel}: column '${field}' has no width and no flex+minWidth — MUI's 100px default ` +
          "clips the first wide value, and a flex without a floor collapses under it",
      );
    }
    index = close;
  }
  return issues;
}

/** The head's filter row wraps: six boxes at 1400px put the last select off-screen (x=1530). */
function checkListHeadWraps(): string[] {
  const source = readIfPresent(join(frontendSrc, "components", "data-grid", "ListCardHead.tsx"));
  if (source === null || /flexWrap="wrap"/.test(source)) return [];
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
  if (!/problemOf\(/.test(content) || !/refusal\(/.test(content)) {
    issues.push(
      `${fileLabel}: has no problemOf/refusal pair — the red cell and the sentence a blocked ` +
        "save shows must come from one function, or they disagree",
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
  if (/\bonRowClick=/.test(content)) {
    issues.push(
      `${fileLabel}: onRowClick on a list grid — a row that opens a record cannot ` +
        "also be a row a user types into; put the intent in rowActionsColumn",
    );
  }
  issues.push(...checkActionCountBudget(fileLabel, content));
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

/** A tab that fetches refetches on every tab switch and can disagree with its siblings. */
function checkDetailTab(fileLabel: string, content: string): string[] {
  if (/from ['"]@\/lib\/api\/hooks\//.test(content)) {
    return [
      `${fileLabel}: a detail tab queries its own data — take the entity as a prop ` +
        "so every tab shows one version of the row",
    ];
  }
  return [];
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
