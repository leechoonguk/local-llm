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
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

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
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);

/** The one module allowed to spell a colour. */
const PALETTE_OWNER = "frontend/src/theme/palette.ts";

/** The one module allowed to spell a shadow. */
const SHADOW_OWNER = "frontend/src/theme/shadows.ts";

/** Layout metrics live in config.ts; these are the numbers that must not recur. */
const LAYOUT_LITERALS: Record<string, string> = {
  "280": "NAV.W_DASHBOARD",
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
  issues.push(...checkGlyphPointerEvents());
  issues.push(...checkAutoMarginInsideSpacedStack());
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

/** The ported design modules must exist and be wired into the theme. */
function checkDesignModules(): string[] {
  const issues: string[] = [];
  const required = ["palette.ts", "typography.ts", "shadows.ts", "overrides.ts", "index.tsx"];
  for (const name of required) {
    if (!existsSync(join(frontendSrc, "theme", name))) {
      issues.push(`frontend/src/theme/${name}: missing — the design system is incomplete`);
    }
  }

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
