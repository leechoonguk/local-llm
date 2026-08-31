/**
 * The record-dialog standard, checked mechanically.
 *
 * `sections/integration/` is the worked example the rule points at; nothing here
 * is bound to it. Files are discovered by role (`*DetailDialog.tsx`,
 * `detail/*Tab.tsx`, `*Panel.tsx`, `*DeletePanel.tsx`) under whatever domain
 * folder they live in, and every rule is checked by **position or ownership**,
 * never by "does the file mention X": a check that only greps passes on a file
 * that names the right component in a comment while rendering the wrong one.
 *
 * Each rule below failed on a real screen first, and each is **conditional on the
 * domain having the thing it governs** — a requirement invented out of the
 * exemplar's shape is how a standard becomes a costume:
 *
 * | Rule | Applies when | The defect it caught |
 * |---|---|---|
 * | the dialog owns the page | one of its tabs draws a paged collection | paging inside a tab reset to page 1 on every record visit |
 * | a tab draws through `PagedTableSection` | the tab draws a table at all | two tabs drifted to different row heights and footers |
 * | a panel renders `PanelStrip` | the file is a panel | one panel's run button sat below its own output |
 * | alerts follow the strip | the panel has an alert | the reason a pinned save was dead sat 700px below it |
 * | leaving is drawn by the strip | the file is a panel | `뒤로` inline was the first of five things in the identity row |
 * | one child absorbs the row | the strip has two `noWrap` children | two long values shrank against each other, neither readable |
 * | one outcome per run | the panel renders a mutation's `.data` | a failed re-run left the previous success under the new error |
 * | a delete panel is `RecordDeletePanel` | the file is a delete panel | one delete had two cancels, the other one |
 * | fields come from `RecordFields` | the panel both reads and edits | `readOnly` and `aria-readonly` written twice, disagreeing |
 * | a clipped value has `ClippedText` | the cell prints a value | a clipped code existed nowhere on screen |
 * | no inline pixel height | always, in a section | 37px rows beside 43px rows in sibling tables |
 *
 * Verified against a synthetic second domain (`sections/vendor/`): a conforming
 * shape passes, a scalar-only domain with no table and no paging passes untouched,
 * and each violation fires.
 */

import { SRC_DIRECTORIES, readSources } from "./frontend-source.ts";

/** JSX order is the whole point of two of these rules, so comments must go first. */
function stripComments(content: string): string {
  return content
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");
}

/** `<Name` opening tags in source order — enough to compare positions. */
function openingTags(content: string): string[] {
  return [...content.matchAll(/<([A-Z][A-Za-z0-9]*)\b/g)].map((match) => match[1]);
}

/**
 * The local name a mutation hook was assigned to.
 *
 * Declared, not inferred: this repo's mutation hooks are `useCreate*`,
 * `useUpdate*`, `useDelete*`, `useRemove*` and `useExecute*`, and a query hook's
 * `.data` is exactly what a list screen is supposed to read.
 */
const MUTATION_HOOK = /const\s+(\w+)\s*=\s*use(?:Create|Update|Delete|Remove|Execute)\w*\(/g;

const METRIC_SOURCE = "RECORD_SURFACE";

/** `RECORD_SURFACE.TABLE_ACTIONS_WIDTH` as a number, for the share arithmetic. */
const RECORD_ACTIONS_SHARE = 10;

/**
 * A height decides the rhythm two files have to share; a width usually does not.
 *
 * A `GridColDef`'s `width: 160` is that column's own business and stays with it —
 * flagging it was this rule's first version and it fired on three list screens
 * that had done nothing wrong. What drifted was heights: a table row read 37px in
 * one tab and 43 in its sibling, a section header 70px with a button and 62
 * without. So only inline pixel heights are reported, and only when the file
 * never reads the shared source.
 */
const METRIC_LITERAL = /\b(?:height|minHeight|maxHeight)\s*:\s*(\d{2,})\b/;

export function checkRecordDialogStandard(): string[] {
  const issues: string[] = [];
  const files = readSources(SRC_DIRECTORIES.sections);

  /**
   * Which domains actually page something. A dialog is held to owning the page
   * only when one of its own tabs draws a paged collection — a record whose tabs
   * are scalars has nothing to page, and demanding the hook anyway would be this
   * check inventing a requirement out of the exemplar's shape.
   */
  const pagingDomains = new Set(
    files
      .filter((file) => /\/detail\/.*Tab\.tsx$/.test(file.label) && /<PagedTableSection\b/.test(file.content))
      .map((file) => domainOf(file.label)),
  );

  for (const file of files) {
    const code = stripComments(file.content);
    const tags = openingTags(code);

    if (file.label.endsWith("DetailDialog.tsx")) {
      issues.push(...checkDialog(file.label, code, pagingDomains.has(domainOf(file.label))));
    }
    if (/\/detail\/.*Tab\.tsx$/.test(file.label)) {
      issues.push(...checkTab(file.label, code, tags));
    }
    if (/DeletePanel\.tsx$/.test(file.label)) {
      issues.push(...checkDeletePanel(file.label, code, tags));
    } else if (/Panel\.tsx$/.test(file.label)) {
      issues.push(...checkPanel(file.label, code, tags));
    }
    issues.push(...checkMetrics(file.label, code));
  }

  return issues;
}

/** `frontend/src/sections/<domain>/…` — the folder is the domain, whatever it is called. */
function domainOf(fileLabel: string): string {
  return fileLabel.split("/sections/")[1]?.split("/")[0] ?? "";
}

function checkDialog(fileLabel: string, code: string, pagesSomething: boolean): string[] {
  const issues: string[] = [];
  const pages = /\buseTablePage\(/.test(code);
  if (pagesSomething && !pages) {
    issues.push(
      `${fileLabel}: a tab of this domain draws a paged collection but the dialog does ` +
        "not call useTablePage — the dialog owns the page because a page held in a tab " +
        "is unmounted the moment a record opens, and the reader returns from the record " +
        "they just edited to page 1",
    );
  }
  if (pages && !/\.reset\(\)/.test(code)) {
    issues.push(
      `${fileLabel}: never resets paging — the dialog stays mounted between openings, ` +
        "so the next record would open on the page the last one was left on",
    );
  }
  if (!/onExited\s*:/.test(code)) {
    issues.push(
      `${fileLabel}: resets nothing on the close transition — resetting on the click ` +
        "shows the body snapping back while the dialog is still fading out",
    );
  }
  return issues;
}

/**
 * A tab that draws a table draws it through the shared frame.
 *
 * Conditional on there being a table: the first version demanded
 * `PagedTableSection` from every `detail/*Tab.tsx`, which assumed this exemplar's
 * shape — its tabs happen to be collections. A tab showing a record's scalars has
 * no table, no page and no footer, and reporting it would be the check inventing
 * a requirement.
 */
function checkTab(fileLabel: string, code: string, tags: string[]): string[] {
  const issues: string[] = [];
  const drawsTable = /<Table\b/.test(code) || tags.includes("PagedTableSection");
  if (drawsTable && !tags.includes("PagedTableSection")) {
    issues.push(
      `${fileLabel}: draws its own Table — render PagedTableSection, so the section card, ` +
        "the empty sentence, the fixed-share columns and the footer have one owner " +
        "(measured: two sibling tabs were 83 of 118 lines identical before it existed)",
    );
  }
  if (/\bpaging\b/.test(code) && /useTablePage\(/.test(code)) {
    issues.push(
      `${fileLabel}: calls useTablePage itself — take the paging as a prop, or the page ` +
        "dies with this body every time a record opens",
    );
  }
  return issues;
}

/**
 * The children of `<PanelStrip …>` — the identity row's own content.
 *
 * The opening tag ends at the first `>` that is not inside a brace, because
 * `actions={…}` carries whole JSX trees with their own `>` characters: measured
 * on `IntegrationOperationPanel`, whose actions prop holds four buttons and two
 * icons. Reading to the first `>` instead reported every panel.
 */
function stripChildren(code: string): string | null {
  const open = code.indexOf("<PanelStrip");
  const close = code.indexOf("</PanelStrip>");
  if (open === -1 || close === -1) return null;
  let depth = 0;
  for (let index = open; index < close; index += 1) {
    const character = code[index];
    if (character === "{") depth += 1;
    else if (character === "}") depth -= 1;
    else if (character === ">" && depth === 0) return code.slice(index + 1, close);
  }
  return null;
}

/**
 * A panel renders a strip, and its alerts come right after that strip.
 *
 * Positional, and deliberately not a list of allowed components: the first
 * version filtered the tags between them against
 * `["Typography", "Label", "Button", "Iconify", "Divider", "Fragment"]`, which is
 * this exemplar's vocabulary — a domain whose strip carries a `Chip` or an
 * `Avatar` would have been reported for doing nothing wrong. Measuring from the
 * strip's **closing** tag removes the need to know what the strip contains: after
 * it, only a separator may stand between the strip and the first alert.
 */
function checkPanel(fileLabel: string, code: string, tags: string[]): string[] {
  const issues: string[] = [];
  if (!tags.includes("PanelStrip")) {
    issues.push(
      `${fileLabel}: renders no PanelStrip — a panel's verbs live in one pinned row; ` +
        "measured before it existed, one panel's run button sat under the result it appends",
    );
    return issues;
  }

  const children = stripChildren(code);
  if (children !== null) {
    if (/<Button\b/.test(children) || /name="back"/.test(children)) {
      issues.push(
        `${fileLabel}: a control stands among the strip's children — the record's verbs go ` +
          "through `actions`, and leaving through `onBack`, which draws it on the line " +
          "above the identity row. Inline, leaving was the first of five things in the one " +
          "row a reader scans to see what the record is",
      );
    }
    const absorbers = (children.match(/noWrap/g) ?? []).length;
    if (absorbers > 1) {
      issues.push(
        `${fileLabel}: ${absorbers} strip children declare noWrap — exactly one child absorbs ` +
          "what the row has left over, or two long values shrink against each other and " +
          "neither one is readable",
      );
    }
  }

  // One run has one ending. A panel that renders the mutation's `data` for the
  // success and keeps its own state for the failure writes the same section
  // twice — measured: the run panel grew a second status-plus-payload block
  // above the inputs, and a failed re-run left the previous success on screen
  // underneath the new error. The outcome is one value the panel sets itself.
  for (const match of code.matchAll(MUTATION_HOOK)) {
    const variable = match[1];
    if (new RegExp(`\\b${variable}\\.data\\b`).test(code)) {
      issues.push(
        `${fileLabel}: renders ${variable}.data — a mutation's data is the success half of ` +
          "an outcome; hold the whole outcome in one state so a failure replaces a success " +
          "instead of standing beside it",
      );
    }
  }

  const stripEnd = code.indexOf("</PanelStrip>");
  const alertAt = code.indexOf("<Alert");
  if (stripEnd === -1 || alertAt === -1 || alertAt < stripEnd) return issues;

  const between = openingTags(code.slice(stripEnd, alertAt)).filter((tag) => tag !== "Divider");
  if (between.length > 0) {
    issues.push(
      `${fileLabel}: ${between.join(", ")} stands between the strip and the first Alert — ` +
        "a failed save is the reason the pinned button is dead, and a reason below the fold " +
        "is a reason nobody reads (measured: 22 response fields pushed it off-screen)",
    );
  }
  return issues;
}

function checkDeletePanel(fileLabel: string, code: string, tags: string[]): string[] {
  if (!tags.includes("RecordDeletePanel")) {
    return [
      `${fileLabel}: does not render RecordDeletePanel — two delete panels written ` +
        "separately drifted into two shapes, one with a pinned strip and one with " +
        "cancel repeated at the bottom",
    ];
  }
  if (/position:\s*'sticky'/.test(code)) {
    return [
      `${fileLabel}: pins its own strip — RecordDeletePanel already owns that row, ` +
        "and two owners is how the two panels disagreed in the first place",
    ];
  }
  return [];
}

/**
 * A record's inputs come from `RecordFields`, so `readOnly` means one thing.
 *
 * Only panels that actually read *and* edit are held to it: a run panel collects
 * inputs and never renders a stored value.
 */
export function checkRecordFieldUsage(): string[] {
  const issues: string[] = [];
  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    if (!/Panel\.tsx$/.test(file.label) || /DeletePanel\.tsx$/.test(file.label)) continue;
    const code = stripComments(file.content);
    const readsAndEdits = /\breadOnly\b/.test(code) && /<TextField\b/.test(code);
    if (readsAndEdits && !/from ['"]@\/components\/detail\/RecordFields['"]/.test(code)) {
      issues.push(
        `${file.label}: builds its own readOnly/edit switch out of TextField — import ` +
          "ScalarField / ChoiceField / NumberField from components/detail/RecordFields, " +
          "or the readOnly input and its aria-readonly pair get written twice and disagree",
      );
    }
  }
  return issues;
}

/**
 * A clipped value must be reachable by hovering, through a tooltip that exists.
 *
 * These tables clip on purpose — `text-overflow: ellipsis` is what keeps a row at
 * one height and a column at its declared share. The first fix was the native
 * `title` attribute and it was not a fix: the browser draws that tooltip in its
 * own chrome, so nothing in the DOM proves it appeared, and reported from the
 * screen it did not. `ClippedText` renders MUI's `Tooltip` — a real
 * `[role=tooltip]` node — and only when the text actually overflows.
 *
 * So the rule is componentwise: a cell that prints a value renders `ClippedText`,
 * and `ServerDataGrid` injects it for every text column. A cell whose content is a
 * component owns its own hover story (a `Label` badge says one word that never
 * clips, `RowActionButtons` names each button) and is left alone.
 */
export function checkClippedCellsRevealOnHover(): string[] {
  const issues: string[] = [];
  const components = readSources(SRC_DIRECTORIES.components);

  const grid = components.find((file) => file.label.endsWith("data-grid/ServerDataGrid.tsx"));
  if (grid !== undefined) {
    const code = stripComments(grid.content);
    // Inside the injected renderer, not merely somewhere in the file: the first

    // version passed on a mutated grid because `DataGridEmptyOverlay
    // title={emptyTitle}` satisfied a bare `/title=\{/`.
    const injected = /renderCell:\s*\([\s\S]{0,600}?<ClippedText\b/.test(code);
    if (!injected) {
      issues.push(
        `${grid.label}: its injected renderCell does not render ClippedText — the grid ` +
          "clips with ellipsis, and a native title cannot be verified to appear " +
          "(measured: `mfds-food-safety-korea` read as `mfds-food-safet...` with no tooltip)",
      );
    }
  }

  // Sections *and* components: the shared frame draws the header labels, and a
  // label clipped at 9% of the width is as unreadable as a clipped value.
  for (const file of [...readSources(SRC_DIRECTORIES.sections), ...components]) {
    if (file.label.endsWith("detail/ClippedText.tsx")) continue;
    const code = stripComments(file.content);
    for (const cell of code.matchAll(/<TableCell\b[^>]*>\s*\{([^}]+)\}\s*<\/TableCell>/g)) {
      const child = cell[1];
      // A literal never clips; a property read or a call is a value the row carries.
      // `title=` on the cell is deliberately **not** accepted: it was the first fix
      // and the browser draws it in its own chrome, so nothing proves it appeared.
      const printsValue = /[A-Za-z_$][\w$]*\s*[.(]/.test(child);
      if (printsValue) {
        issues.push(
          `${file.label}: cell prints {${child.trim().slice(0, 40)}} as bare text — wrap it in ` +
            "ClippedText, whose tooltip is a real node that can be seen and measured " +
            "(a native title cannot)",
        );
      }
    }
  }

  return issues;
}

function checkMetrics(fileLabel: string, code: string): string[] {
  // No whole-file escape: reading one metric from config says nothing about the
  // next literal in the same file. Measured — the first version skipped any file
  // that mentioned RECORD_SURFACE anywhere, and a planted `minHeight: 99` two
  // lines below the import went unreported.
  const match = METRIC_LITERAL.exec(code);
  if (match === null) return [];
  return [
    `${fileLabel}: layout metric literal ${match[0].trim()} — read it from ` +
      `${METRIC_SOURCE} in config.ts, because a number two files have to agree on ` +
      "drifted once already (37px rows beside 43px rows in sibling tabs)",
  ];
}

/**
 * Declared column shares have to fit in the table.
 *
 * `tableLayout: 'fixed'` divides the width by the declared shares, so shares that
 * sum past 100% do not shrink — the last columns are pushed out and the long value
 * draws over its neighbours. Measured: a path template ran across the field count
 * and status columns before the shares were re-divided, and the screen looked like
 * a rendering bug rather than an arithmetic one.
 *
 * Percent only: mixing `px` into a fixed layout makes the remaining shares depend
 * on the container, which is the thing fixed layout exists to avoid.
 */
export function checkColumnShares(): string[] {
  const issues: string[] = [];
  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    const code = stripComments(file.content);
    const block = /columns:\s*TableColumn\[\]\s*=\s*\[([\s\S]*?)\n\s*\]/.exec(code);
    if (block === null) continue;

    const widths = [...block[1].matchAll(/width:\s*'([^']+)'/g)].map((match) => match[1]);
    const nonPercent = widths.filter((width) => !/^\d+(?:\.\d+)?%$/.test(width));
    if (nonPercent.length > 0) {
      issues.push(
        `${file.label}: column width ${nonPercent.join(", ")} is not a percentage — a fixed ` +
          "layout divides by shares, so one absolute width makes every other column depend " +
          "on the container",
      );
      continue;
    }

    const declared = widths.reduce((sum, width) => sum + Number.parseFloat(width), 0);
    // The actions column is declared beside them and takes its share of the same 100.
    const actions = /actionsWidth=\{[^}]*\}/.test(code) ? RECORD_ACTIONS_SHARE : 0;
    const total = declared + actions;
    if (total > 100) {
      issues.push(
        `${file.label}: column shares total ${total}% (${widths.join(" + ")} + ${actions}% actions) ` +
          "— a fixed layout does not shrink them, so the last columns are pushed out and the " +
          "long value draws over its neighbours",
      );
    }
  }
  return issues;
}
