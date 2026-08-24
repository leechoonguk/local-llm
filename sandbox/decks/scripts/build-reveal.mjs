#!/usr/bin/env node
// Build a single-file reveal.js deck from a Marp-style markdown source.
// - slides.md keeps the same format: `---` separates slides
// - output HTML embeds each slide as <section data-markdown> so it opens
//   from file:// with no build tools or web server
// - mermaid code fences render via the reveal.js mermaid plugin (CDN)
//
// Usage: node scripts/build-reveal.mjs <deck-dir> [--theme <name>]
//   theme: black | white | league | beige | sky | night | serif |
//          simple | solarized | moon | dracula (default: dracula)
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const args = process.argv.slice(2);
const themeIdx = args.indexOf("--theme");
const THEME = themeIdx !== -1 && args[themeIdx + 1] ? args[themeIdx + 1] : "dracula";
const deckDirs = args.filter((_, i) => i !== themeIdx && i !== themeIdx + 1);
const REVEAL_VERSION = "5.2.1";

function buildDeck(deckDir) {
  const srcPath = join(deckDir, "slides.md");
  if (!existsSync(srcPath)) {
    console.error(`SKIP (deck not found): ${srcPath}`);
    return;
  }
  let md = readFileSync(srcPath, "utf8");

  // Strip the YAML headmatter (frontmatter block at the very start).
  md = md.replace(/^---\n[\s\S]*?\n---\n/, "");

  // Strip the sync-hash comment block (<!-- sync: ... -->) — the source
  // keeps it for check-decks-sync, the rendered HTML does not need it.
  md = md.replace(/<!-- sync: [^\n]* -->\n?/g, "");

  // Split into slides. A line that is exactly `---` (or `--- ` with
  // trailing spaces) separates slides.
  const slides = md.split(/\n---+\s*\n/).map((s) => s.trim());

  const sections = slides
    .map((slide) => {
      // Inside <script type="text/template">, HTML entities are NOT decoded
      // by the markdown plugin's parser twice — escaping < as &lt; here
      // produces double-encoded text (&amp;lt;) that breaks mermaid and
      // inline HTML. Only guard the script terminator.
      const escaped = slide.replace(/<\/script>/gi, "<\\/script>");
      return `      <section data-markdown>\n        <script type="text/template">\n${escaped}\n        </script>\n      </section>`;
    })
    .join("\n\n");

  const html = `<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${deckDir.split("/").pop()}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/reveal.css" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/theme/${THEME}.css" id="theme" />
  <style>
    .reveal section img { max-height: 60vh; }
    .reveal table { font-size: 0.75em; margin: 0 auto; }
    .reveal table th { background: rgba(255,255,255,0.12); }
    .reveal .mermaid { background: transparent; }
    .reveal pre code { max-height: 60vh; }
  </style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
${sections}
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/dist/reveal.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/plugin/markdown/markdown.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@${REVEAL_VERSION}/plugin/notes/notes.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    // Disable mermaid auto-render: it would render hidden slides as empty
    // SVGs (NaN coordinates) before reveal.js marks them visible. Our
    // renderMermaid below renders only the present slide on demand.
    mermaid.initialize({ startOnLoad: false });
    Reveal.initialize({
      hash: true,
      slideNumber: true,
      transition: 'none', // avoids mid-transition layout glitches in mermaid
      plugins: [RevealMarkdown, RevealNotes],
    });
    // Render mermaid only for the visible slide. Mermaid fails with NaN
    // coordinates inside hidden (display:none) slides and mid-transition,
    // so render on ready/slidechanged with retries until the layout settles.
    const renderMermaid = async (attempt = 0) => {
      const slide = document.querySelector('.reveal .slides section.present');
      if (!slide || slide.dataset.mermaidDone) return;
      // reveal.js markdown renders the fence as code.mermaid (no
      // language- prefix); match both forms.
      const blocks = slide.querySelectorAll('pre code.language-mermaid, pre code.mermaid');
      if (!blocks.length) { slide.dataset.mermaidDone = '1'; return; }
      let allRendered = true;
      for (const code of blocks) {
        try {
          const { svg } = await mermaid.render('rm-' + Math.random().toString(36).slice(2), code.textContent);
          const wrapper = document.createElement('div');
          wrapper.className = 'mermaid';
          wrapper.innerHTML = svg;
          code.replaceWith(wrapper);
        } catch (e) {
          allRendered = false;
        }
      }
      if (allRendered) {
        slide.dataset.mermaidDone = '1';
      } else if (attempt < 3) {
        setTimeout(() => renderMermaid(attempt + 1), 400);
      }
    };
    Reveal.on('ready', () => setTimeout(renderMermaid, 300));
    Reveal.on('slidechanged', () => setTimeout(renderMermaid, 300));
  </script>
</body>
</html>
`;
  const outPath = join(deckDir, "slides.html");
  writeFileSync(outPath, html);
  console.log(`BUILT: ${outPath} (theme=${THEME}, ${slides.length} slides)`);
}

for (const deckDir of deckDirs) {
  buildDeck(deckDir);
}
