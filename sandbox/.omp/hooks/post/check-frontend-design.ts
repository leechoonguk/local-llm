import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import {
  SRC_DIRECTORIES,
  frontendSrc,
  readIfPresent,
  readSources,
} from "../lib/frontend-source.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";

/**
 * Check-Frontend-Design Post Hook
 *
 * Validates the design system from .omp/rules/frontend-design.md. The palette,
 * the type scale and the shadows are ported values; this keeps them the only
 * source:
 *
 *   1. no colour literal (#hex, rgb(), hsl()) outside theme/palette.ts
 *   2. no `boxShadow:` string in a component — customShadows owns them
 *   3. no `fontSize`/`fontWeight` literal — a typography variant owns them
 *   4. no layout metric literal (nav width, header height) outside config.ts
 *   5. `Chip` is not a status badge — `Label` is
 *   6. `styles.css` carries a reset, never page layout
 *   7. the design modules themselves exist and are wired into the theme
 *
 * This is a read-only check — it does NOT block tool calls.
 */

/** The one module allowed to spell a colour. */
const PALETTE_OWNER = "frontend/src/theme/palette.ts";

/** The one module allowed to spell a shadow. */
const SHADOW_OWNER = "frontend/src/theme/shadows.ts";

/** Layout metrics live in config.ts; these are the numbers that must not recur. */
const LAYOUT_LITERALS: Record<string, string> = {
  "280": "NAV.W_DASHBOARD",
  "88": "NAV.W_MINI",
  "92": "HEADER.H_DESKTOP",
  "64": "HEADER.H_MOBILE",
};

const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgb\(|\bhsl\(/;

/** A spelled shadow. `boxShadow: 'none'` removes one and spells nothing. */
const SHADOW_LITERAL = /boxShadow:\s*['"`](?!none['"`])/;

/**
 * A raw Iconify id passed as an icon. Matched at the prop, not anywhere a
 * `family:name` string could appear — an event name (`auth:session-expired`)
 * has the same shape and is not an icon.
 */
const ICON_LITERAL = /\bicon=\s*\{?["'`][a-z0-9-]+:[a-z0-9-]+["'`]/

const FONT_LITERAL = /\bfont(?:Size|Weight):\s*(?:\d|['"`])/;

/** The one module allowed to spell an icon id or an asset path. */
const ICON_OWNER = "frontend/src/components/iconify/icons.ts"

/** A layout metric used as a width/height/offset, not as a page size or a colour. */
const LAYOUT_METRIC = /(?:width|height|pt|pb|py|top|marginTop):\s*[`'"]?\s*(\d{2,3})\b/g;

export default function checkFrontendDesign(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-frontend-design", event, () => {
    if (!touchesPath(event, ["frontend/"])) return;
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkFrontendDesignSync();
    if (issues.length === 0) {
      resetSuppression("check-frontend-design");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-frontend-design",
      issues,
      "run make check-frontend-design for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-frontend-design") };
  }));
}

export function checkFrontendDesignSync(): string[] {
  const issues: string[] = [];
  if (!existsSync(frontendSrc)) return ["frontend/src/: directory not found"];

  issues.push(...checkDesignModules());
  issues.push(...checkStylesheet());

  for (const file of readSources(frontendSrc)) {
    const isPalette = file.label === PALETTE_OWNER;
    const isShadow = file.label === SHADOW_OWNER;
    const isTheme = file.label.startsWith("frontend/src/theme/");

    file.content.split("\n").forEach((line: string, index: number) => {
      const position = `${file.label}:${index + 1}`;
      if (!isPalette && COLOR_LITERAL.test(line)) {
        issues.push(
          `${position}: colour literal — read a token (primary.main, text.secondary) ` +
            `or tint one with alpha(); ${PALETTE_OWNER} owns the values`,
        );
      }
      if (!isShadow && !isTheme && SHADOW_LITERAL.test(line)) {
        issues.push(
          `${position}: boxShadow string — use theme.customShadows.* so it matches ` +
            "the cards beside it",
        );
      }
      if (!isTheme && FONT_LITERAL.test(line)) {
        issues.push(
          `${position}: font size/weight literal — pick a typography variant; the ` +
            "scale is responsive and a literal is not",
        );
      }
      if (file.label !== ICON_OWNER && ICON_LITERAL.test(line)) {
        issues.push(
          `${position}: raw icon id — add it to ${ICON_OWNER} and reference the name, ` +
            "or the app grows a second icon family one screen at a time",
        );
      }
      if (!isTheme) issues.push(...checkLayoutLiterals(position, line, file.label));
    });
  }

  issues.push(...checkStatusBadge());
  issues.push(...checkDetailSurface());
  issues.push(...checkCardGap());
  issues.push(...checkGlyphPointerEvents());
  issues.push(...checkAutoMarginInsideSpacedStack());
  issues.push(...checkThemeDefaults());
  issues.push(...checkNavGlyphsAreDistinct());
  issues.push(...checkSurfacesHaveBothModes());
  return issues;
}

/**
 * Two defaults the theme owns because MUI's own were measured wrong here.
 *
 * - `MuiSelect` and `MuiAutocomplete` bound their popups to the same constant:
 *   without `maxHeight` the 상태 filter's 86
 *   values stood 804px tall from the top of the screen, detached from the box
 *   that opened it. The number is `SELECT_MENU_MAX_HEIGHT` in config.ts, read
 *   there and not typed into the override.
 * - `MuiTabs` carries no scroll arrows: MUI shows them when the first or last
 *   tab is under 99 % inside the scroller, and a dialog re-centred on a
 *   fractional height lit both arrows over a four-tab strip with nothing to
 *   scroll. A strip that does overflow still scrolls by swipe.
 */
function checkThemeDefaults(): string[] {
  // existence-ok: checkDesignModules reports the theme module that is missing.
  const overrides = readIfPresent(join(frontendSrc, "theme", "overrides.ts"));
  if (overrides === null) return [];
  const issues: string[] = [];
  const select = /MuiSelect:\s*\{[\s\S]*?\n\s{4}\}/.exec(overrides)?.[0] ?? "";
  if (!/maxHeight:\s*SELECT_MENU_MAX_HEIGHT/.test(select)) {
    issues.push(
      "frontend/src/theme/overrides.ts: MuiSelect has no default MenuProps with " +
        "maxHeight: SELECT_MENU_MAX_HEIGHT — a long vocabulary's menu takes the viewport " +
        "and leaves the box that opened it (measured: 86 values, 804px, from y=80)",
    );
  }
  const autocomplete = /MuiAutocomplete:\s*\{[\s\S]*?\n\s{4}\}/.exec(overrides)?.[0] ?? "";
  if (!/maxHeight:\s*SELECT_MENU_MAX_HEIGHT/.test(autocomplete)) {
    issues.push(
      "frontend/src/theme/overrides.ts: MuiAutocomplete's listbox has no " +
        "maxHeight: SELECT_MENU_MAX_HEIGHT — MUI gives it 40vh, which is a different height on " +
        "every screen, while the Select beside it is bounded by the constant",
    );
  }
  const tabs = /MuiTabs:\s*\{[\s\S]*?\n\s{4}\}/.exec(overrides)?.[0] ?? "";
  if (!/scrollButtons:\s*false/.test(tabs)) {
    issues.push(
      "frontend/src/theme/overrides.ts: MuiTabs does not default scrollButtons: false — " +
        "MUI lights both arrows when a tab sits half a pixel outside the scroller, over a " +
        "strip with nothing to scroll (measured on the 기준규격 tab)",
    );
  }
  return issues;
}

/**
 * A surface colour has a counterpart in the other mode.
 *
 * The theme is built per mode now, so `background.paper`, `text.primary` and the
 * rest resolve to whatever the reader chose. What does **not** move is a grey or
 * a `common.*` picked by hand: `grey[800]` is a page-dark card in dark mode and
 * near-black text in light, and `common.white` is a surface in one and a glare in
 * the other.
 *
 * So outside `theme/`, a line that paints a background or text with one of those
 * is only allowed in a file that reads `palette.mode` — that is the file saying
 * it knows there are two answers. `alpha(grey[500], …)` is untouched: a tint of
 * the mid grey is the one value that reads on both surfaces, which is why the
 * divider and every hover in the design is built from it.
 */
function checkSurfacesHaveBothModes(): string[] {
  const issues: string[] = [];
  for (const file of readSources(frontendSrc)) {
    if (file.label.startsWith("frontend/src/theme/")) continue;
    const modeAware = /palette\.mode/.test(file.content);
    if (modeAware) continue;
    file.content.split("\n").forEach((line: string, index: number) => {
      const code = line.replace(/\/\/.*$/, "");
      if (!/(?:bgcolor|backgroundColor|color):/.test(code)) return;
      const fixed = /common\.(?:white|black)|grey\[(?:0|100|200|700|800|900)\]/.exec(code);
      if (fixed === null) return;
      // A tint keeps its meaning on either surface; a solid does not.
      if (/alpha\(/.test(code)) return;
      issues.push(
        `${file.label}:${index + 1}: paints with ${fixed[0]}, which is one mode's answer — ` +
          "read a token that moves with the mode (background.paper, text.primary), or " +
          "branch on palette.mode where the two really differ",
      );
    });
  }
  return issues;
}

/**
 * An auto margin inside a `Stack` that spaces with child margins is dead code.
 *
 * `Stack spacing={n}` writes `margin-left: 8n` onto every child after the first,
 * from a selector on the parent — which outranks the child's own `sx`. So
 * `<Stack spacing={1.5}><Thing sx={{ ml: 'auto' }} /></Stack>` computes to
 * `margin-left: 12px` and the child does not move. Measured on the panel strip:
 * the actions group carried `ml: 'auto'`, the doc comment said "pushed to the
 * right edge of the row", and `저장 취소` sat against the method badge with 457px
 * of empty row to its right for as long as the component existed. `useFlexGap`
 * switches the parent to `gap` and removes the margins, so the child moves.
 *
 * Attribution is exact rather than textual: the auto margin is read while the
 * scanner is inside a child's opening tag, so the element it belongs to is the
 * one on top of the open-tag stack — its parent.
 */
function checkAutoMarginInsideSpacedStack(): string[] {
  const issues: string[] = [];
  const AUTO_MARGIN = /\b(?:ml|marginLeft|mr|marginRight|mx):\s*['"`]auto['"`]/;
  for (const root of [SRC_DIRECTORIES.components, SRC_DIRECTORIES.sections, SRC_DIRECTORIES.layouts]) {
    for (const file of readSources(root)) {
      // Comments are blanked to spaces, not deleted: line numbers stay true
      // while a comment can no longer answer — or accuse — for code. Measured:
      // the panel strip's own comment names the `ml: 'auto'` it explains, and
      // the first version of this check reported the component it documents.
      const code = file.content
        .replace(/\{\/\*[\s\S]*?\*\/\}|\/\*[\s\S]*?\*\//g, (match) => match.replace(/[^\n]/g, " "))
        .replace(/\/\/[^\n]*/g, (match) => " ".repeat(match.length));
      const open: Array<{ name: string; marginSpaced: boolean }> = [];
      let index = 0;
      while (index < code.length) {
        const tag = /^<(\/?)([A-Z][A-Za-z0-9.]*)/.exec(code.slice(index));
        if (tag === null) {
          index += 1;
          continue;
        }
        if (tag[1] === "/") {
          open.pop();
          index += tag[0].length;
          continue;
        }
        // Collect the opening tag's attributes: its own `>` characters can sit
        // inside `{...}` props (an `actions={<Button/>}` tree), so depth counts.
        let cursor = index + tag[0].length;
        let depth = 0;
        while (cursor < code.length) {
          const character = code[cursor];
          if (character === "{") depth += 1;
          else if (character === "}") depth -= 1;
          else if (character === ">" && depth === 0) break;
          cursor += 1;
        }
        const attributes = code.slice(index, cursor);
        const parent = open[open.length - 1];
        if (AUTO_MARGIN.test(attributes) && parent?.name === "Stack" && parent.marginSpaced) {
          const line = code.slice(0, index).split("\n").length;
          issues.push(
            `${file.label}:${line}: <${tag[2]}> sets an auto margin inside a Stack that ` +
              "spaces with child margins — add useFlexGap to the Stack, or the parent's " +
              "margin-left wins and the child never moves",
          );
        }
        if (code[cursor - 1] !== "/") {
          open.push({
            name: tag[2],
            marginSpaced: /\bspacing=/.test(attributes) && !/\buseFlexGap\b/.test(attributes),
          });
        }
        index = cursor + 1;
      }
    }
  }
  return issues;
}

/**
 * The glyph must stay out of the event path.
 *
 * `@iconify/react` re-creates its `<path>` nodes on re-render. Inside a grid cell
 * that happens between `mouseup` and the browser's `click` dispatch — the cell
 * re-renders when it takes focus — so the pressed node is gone and no `click` is
 * ever fired. Measured: every first click on a list screen was dead, with no error
 * anywhere. A reviewer deleting this style as decoration brings the bug back
 * silently, which is exactly what a check is for.
 */
function checkGlyphPointerEvents(): string[] {
  const label = "frontend/src/components/iconify/Iconify.tsx";
  const content = readIfPresent(join(frontendSrc, "components/iconify/Iconify.tsx"));
  if (content === null) return [`${label}: missing`];
  // Comments must not answer for code: the paragraph above this style explains it,
  // and matching that text passed the check with the style itself deleted.
  const code = content.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  if (/pointerEvents:\s*['"`]none['"`]/.test(code)) return [];
  return [
    `${label}: the glyph must carry pointerEvents: 'none' — a re-rendered icon ` +
      "swallows the click that pressed it, and the button reports nothing",
  ];
}

/** The header height and nav width must be read, not retyped. */
function checkLayoutLiterals(position: string, line: string, fileLabel: string): string[] {
  if (fileLabel === "frontend/src/config.ts") return [];
  const issues: string[] = [];
  for (const match of line.matchAll(LAYOUT_METRIC)) {
    const constant = LAYOUT_LITERALS[match[1]];
    if (constant !== undefined) {
      issues.push(
        `${position}: layout metric ${match[1]} — import ${constant} from @/config, or ` +
          "the fixed header covers content on the screen nobody adjusted",
      );
    }
  }
  return issues;
}

/**
 * Every nav item draws its own glyph.
 *
 * The icon column is the sidebar's fastest read - a reader aims at the shape,
 * not the word - and a shape shared by four items says nothing about which row
 * it is. Measured: `food_chat`, `food_item_report`, `food_item_report_event` and
 * `food_raw_material` all pointed at `ic_food.svg`, so half the sidebar was one
 * drawing and every gate was green, because each name existed in the registry
 * and each file existed on disk.
 *
 * Read off `config-navigation.tsx`, which is where a screen picks its glyph.
 */
function checkNavGlyphsAreDistinct(): string[] {
  const label = "frontend/src/layouts/dashboard/config-navigation.tsx";
  const content = readIfPresent(join(frontendSrc, "layouts/dashboard/config-navigation.tsx"));
  if (content === null) return [`${label}: missing — the navigation model lives here`];
  const issues: string[] = [];
  const owner = new Map<string, string>();
  for (const match of content.matchAll(/titleKey:\s*'([\w.]+)'[^}]*icon:\s*'(\w+)'/g)) {
    const [, title, icon] = match;
    const first = owner.get(icon);
    if (first === undefined) {
      owner.set(icon, title);
      continue;
    }
    issues.push(
      `${label}: ${first} and ${title} both draw '${icon}' — a glyph two items share ` +
        "says nothing about which row it is",
    );
  }
  return issues;
}

/** A status rendered as a `Chip` is a status that does not match the design. */
function checkStatusBadge(): string[] {
  const issues: string[] = [];
  for (const root of [SRC_DIRECTORIES.sections, SRC_DIRECTORIES.components]) {
    for (const file of readSources(root)) {
      if (file.label.endsWith("/label/Label.tsx")) continue;
      if (/<Chip\b/.test(file.content)) {
        issues.push(
          `${file.label}: renders a Chip — the design's badge is ` +
            "components/label/Label (24px, radius 6, soft tint)",
        );
      }
    }
  }
  return issues;
}

/**
 * A detail dialog's body is the neutral surface; the cards inside it are white.
 * On a white body those cards have no edge, and the record stops looking like a
 * record — the contrast is the pattern, not a preference.
 */
function checkDetailSurface(): string[] {
  const issues: string[] = [];
  for (const file of readSources(SRC_DIRECTORIES.sections)) {
    if (file.label.endsWith("DetailDialog.tsx") && !/background\.neutral/.test(file.content)) {
      issues.push(
        `${file.label}: the detail body is not background.neutral — white section ` +
          "cards on a white body have no edge",
      );
    }
    // `PagedTableSection` renders the `DetailSection` card for both integration
    // tabs; requiring the literal in the tab file would block pulling a duplicated
    // frame out of two files that shared 83 of 118 lines.
    if (
      /\/detail\/.*Tab\.tsx$/.test(file.label) &&
      !/<DetailSection\b/.test(file.content) &&
      !/<PagedTableSection\b/.test(file.content)
    ) {
      issues.push(
        `${file.label}: a detail tab renders neither DetailSection nor PagedTableSection — ` +
          "its content would sit loose on the neutral body instead of in a titled card",
      );
    }
  }
  return issues;
}

/**
 * Two cards in a row need their parent on a gap.
 *
 * `DetailSection` carries no margin on purpose — the gap belongs between two
 * cards, not on one — so a component that returns several cards from a bare
 * fragment draws them touching. Measured on the 품목제조보고 dialog:
 * the 표시사항 tab's two cards stood at 0px while the 기준규격 tab's three,
 * wrapped in `<Stack spacing={2}>`, stood at 16 and 16. Nothing else saw it:
 * every gate was green and the tab strip reads the same either way.
 *
 * So a file that renders two or more cards must return them from a `Stack` that
 * spells a spacing. The root is what matters: a fragment deeper inside is a
 * cell's children or a conditional branch, and neither stacks cards.
 */
function checkCardGap(): string[] {
  const issues: string[] = [];
  const CARD = /<(?:DetailSection|PagedTableSection)\b/g;
  for (const root of [SRC_DIRECTORIES.sections, SRC_DIRECTORIES.components]) {
    for (const file of readSources(root)) {
      const cards = file.content.match(CARD)?.length ?? 0;
      if (cards < 2) continue;
      // The component's own root: the `return (` at one indent level, past any
      // comment lines an author put between it and the element.
      const root_element = file.content.match(
        /\n  return \(\n(?:\s*(?:\/\/[^\n]*|\{\/\*[\s\S]*?\*\/\})\n)*\s*<([A-Za-z]*)/,
      );
      if (root_element === null) continue;
      const tag = root_element[1];
      if (tag === "") {
        issues.push(
          `${file.label}: returns ${cards} cards from a fragment — they draw touching, ` +
            "because DetailSection carries no margin; return them from <Stack spacing={2}>",
        );
        continue;
      }
      if (tag === "Stack" && !/<Stack\s+spacing=\{/.test(file.content)) {
        issues.push(
          `${file.label}: returns ${cards} cards from a Stack with no spacing — ` +
            "a Stack without one is a column of cards that touch",
        );
      }
    }
  }
  return issues;
}

/** The ported design modules must exist and be wired into the theme. */
function checkDesignModules(): string[] {
  const issues: string[] = [];
  const required = ["palette.ts", "typography.ts", "shadows.ts", "overrides.ts", "index.tsx"];
  for (const name of required) {
    if (!existsSync(join(frontendSrc, "theme", name))) {
      issues.push(`frontend/src/theme/${name}: missing — the design system is incomplete`);
    }
  }

  // existence-ok: theme/index.tsx is imported by Providers.tsx — tsc fails loudly without it.
  const theme = readIfPresent(join(frontendSrc, "theme", "index.tsx"));
  if (theme === null) return issues;
  for (const token of ["palette", "typography", "shadows", "customShadows", "componentOverrides"]) {
    if (!new RegExp(`\\b${token}\\b`).test(theme)) {
      issues.push(
        `frontend/src/theme/index.tsx: does not apply ${token} — a token nobody reads ` +
          "is a design decision that does not reach the screen",
      );
    }
  }
  return issues;
}

/** A stylesheet that lays out pages competes with the theme and wins silently. */
function checkStylesheet(): string[] {
  const path = join(frontendSrc, "styles.css");
  const content = readIfPresent(path);
  if (content === null) return ["frontend/src/styles.css: missing"];
  // Comments explain the ban; only declarations violate it.
  const declarations = content.replace(/\/\*[\s\S]*?\*\//g, "")
  if (/max-width|margin:\s*\d+rem auto|display:\s*grid/.test(declarations)) {
    return [
      "frontend/src/styles.css: carries page layout — it clamped the whole document " +
        "to 40rem once; keep it a reset and let the theme lay out",
    ];
  }
  return [];
}

// Direct execution (make check-frontend-design): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-frontend-design.ts")) {
  const issues = checkFrontendDesignSync();
  console.log("==> check-frontend-design");
  if (issues.length === 0) {
    console.log("    PASS: the design system is the only source of colour, type and metrics");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-frontend-design");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
