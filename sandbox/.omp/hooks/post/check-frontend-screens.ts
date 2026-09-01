import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import {
  SRC_DIRECTORIES,
  frontendSrc,
  label,
  projectRoot,
  readIfPresent,
  readSources,
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
 *   list (`<Domain>List.tsx`)       useDataGridState + usePagedRows +
 *                                   ServerDataGrid + useCrudDialog, an error
 *                                   branch and an empty sentence
 *   form (`<Domain>FormDialog.tsx`) useForm + a resolver + FormProvider, values
 *                                   reset on open, no useState field state
 *   detail (a `detail/` subdirectory) pure presenters — a tab fetches nothing
 *   every section                   reports a failed mutation through useToast
 *
 * `ast-grep/rules/frontend-screen/` owns the structural half (no raw DataGrid).
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/** The one component allowed to render MUI's grid. */
const GRID_OWNER = "frontend/src/components/data-grid/ServerDataGrid.tsx";

/** Hooks a list screen cannot be assembled without. */
const LIST_REQUIRED = [
  "useDataGridState",
  "usePagedRows",
  "ServerDataGrid",
  "useCrudDialog",
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
  }

  issues.push(...checkPagesAreThin());
  issues.push(...checkRecordDialogStandard());
  issues.push(...checkRecordFieldUsage());
  issues.push(...checkClippedCellsRevealOnHover());
  issues.push(...checkColumnShares());
  return issues;
}

function checkListScreen(fileLabel: string, content: string): string[] {
  const issues: string[] = [];
  for (const symbol of LIST_REQUIRED) {
    if (!new RegExp(`\\b${symbol}\\b`).test(content)) {
      issues.push(
        `${fileLabel}: no ${symbol} — a list screen is assembled from the same ` +
          `${LIST_REQUIRED.length} pieces so paging and dialogs behave identically`,
      );
    }
  }
  if (!/\bisError\b/.test(content)) {
    issues.push(
      `${fileLabel}: no isError branch — a failed page renders as an empty list, ` +
        "which is the one state a user cannot tell from success",
    );
  }
  if (!/emptyTitle=/.test(content)) {
    issues.push(`${fileLabel}: passes no emptyTitle — the empty state would have no sentence`);
  }
  issues.push(...checkRowActions(fileLabel, content));
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
  return issues;
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
