/**
 * A ledger is not an endpoint of any edge: it declares no `relationship()` and
 * none points at it. An edge joins two derived tables, read at query time -
 * never a `ForeignKey`, and never a `.join(` that spells the columns again in a
 * repository.
 *
 * The ledgers are written over nightly by their own feeds, and one feed's
 * pass must not fail on another's gaps (measured:
 * `food_ledger_common_standard.common_standard_type_code` → I2590 dangles on
 * a quarter of its rows). A ledger stores answers, so it states no question either:
 * measured: fourteen relationships were declared across the ledger
 * models and none was read outside the tests. What a ledger holds reaches a
 * derived table through its feed's pass - the pass that builds the derived row -
 * so the edges left are between derived tables. This lib measures what that
 * shape needs and nothing else checks:
 *
 * 1. no model under a ledger domain declares a `ForeignKey`;
 * 2. no ledger model (`<domain>_ledger_*`) declares a `relationship()`;
 * 3. no relationship in the domain targets a `<Domain>Ledger*` model;
 * 4. every relationship is `viewonly=True` with a
 *    `primaryjoin=` that marks its own side `foreign(...)` - without a
 *    constraint SQLAlchemy has no other way to know the direction, and the
 *    failure is at mapper configuration, i.e. at the first import of the night;
 * 5. a list-valued edge (`Mapped[list[...]]`) says `uselist=True` - measured:
 *    with `foreign()` on the local side the mapper reads the edge
 *    as many-to-one and hands back one object under a `list` annotation;
 * 6. no query layer joins a domain model by its class - `.join(Food…` outside
 *    `models/` is the edge spelled a second time; join along the attribute
 *    (`.outerjoin(FoodX.rel)`), which is where LEFT is chosen;
 * 7. every derivation that resolves a product's registry reads every registry
 *    (`checkRegistriesAgree`).
 *
 * **The domain is discovered, never named.** `food` was written into this file
 * as a constant, and a second domain of ledgers would have been checked by
 * nothing at all while every gate stayed green - the same shape as the defect
 * §7 exists for. A domain is a folder under `models/` holding at least one
 * model whose `__tablename__` starts `<folder>_ledger_`, and its ledger class
 * prefix follows from the folder's name.
 */

// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { APP_LAYERS, balanced, layerFiles } from "./backend-layout.ts";

const projectRoot = existsSync(join(process.cwd(), "backend", "app"))
  ? process.cwd()
  : join(process.cwd(), "..");

const APP_DIR = join(projectRoot, "backend", "app");
const MODELS_DIR = join(APP_DIR, "models");

/**
 * Every backend layer whose files may build a statement — all of `APP_LAYERS`
 * but the models (a model declares, it does not join) and the tests (a test
 * may spell a join to prove a relationship against it).
 */
const QUERY_LAYERS = Object.keys(APP_LAYERS).filter((layer) => layer !== "models" && layer !== "tests");

/** `__tablename__ = "<domain>_ledger_…"` - what marks a folder as a ledger domain. */
const LEDGER_TABLE_OF = (domain: string) =>
  new RegExp(`__tablename__\\s*=\\s*"${domain}_ledger_`);

/**
 * `FoodLedgerRecall` from `food` - a ledger model's name, as an edge reads it.
 *
 * Non-global on purpose: a `/g` regex carries `lastIndex` between `.test()`
 * calls, so the second edge in a file would be asked from where the first
 * stopped. `matchAll` needs its own global copy, made where it is used.
 */
const LEDGER_CLASS_OF = (domain: string) => new RegExp(`\\b${pascal(domain)}Ledger\\w+`);

/** `food` → `Food`, `item_report` → `ItemReport` - the class-name spelling. */
function pascal(name: string): string {
  return name
    .split("_")
    .map((part: string) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

/**
 * Every folder under `models/` that holds ledgers, by its own name.
 *
 * Discovered rather than listed: a second domain added beside `food` is
 * checked the day its first ledger lands, and nobody has to remember this
 * file exists.
 */
function ledgerDomains(): string[] {
  if (!existsSync(MODELS_DIR)) return [];
  return readdirSync(MODELS_DIR, { withFileTypes: true })
    .filter((entry: { isDirectory: () => boolean; name: string }) => entry.isDirectory())
    .map((entry: { name: string }) => entry.name)
    .filter((domain: string) =>
      layerFiles(join(MODELS_DIR, domain)).some((file: string) =>
        LEDGER_TABLE_OF(domain).test(readFileSync(join(MODELS_DIR, domain, file), "utf-8")),
      ),
    )
    .sort();
}

const RELATIONSHIP = /^\s{4}(\w+):\s*Mapped\[([^\n]*?)\]\s*=\s*(?:\(\s*)?relationship\(/gm;

/** How far above an edge its measurement may sit - a comment block, not the file. */
const EVIDENCE_LINES = 14;
const HAND_JOIN_OF = (domains: string[]) =>
  new RegExp(
    `\\.(?:outer)?join\\(\\s*(?:aliased\\()?\\s*(?:${domains.map(pascal).join("|")})\\w+`,
  );

/**
 * The derived table a registry column keys, found by its shape: its
 * `NATURAL_KEY` names more than one column and one of those columns carries a
 * closed vocabulary (`CheckConstraint("report_kind IN (…)")`). In `food` that
 * is `food_item_report` — the product, keyed (report_kind, item_report_no).
 * Found rather than named, so a second domain needs no edit in this file.
 */
function registryOwners(domain: string): Owner[] {
  const modelsDir = join(MODELS_DIR, domain);
  const isLedger = LEDGER_TABLE_OF(domain);
  const owners: Owner[] = [];
  for (const file of layerFiles(modelsDir)) {
    const content = readFileSync(join(modelsDir, file), "utf-8");
    if (isLedger.test(content)) continue;
    const key = NATURAL_KEY.exec(content);
    const vocabulary = KEY_VOCABULARY.exec(content);
    const cls = /^class (\w+)\(/m.exec(content);
    if (key === null || vocabulary === null || cls === null) continue;
    const columns = [...key[1].matchAll(/"(\w+)"/g)].map((match: RegExpMatchArray) => match[1]);
    const kind = vocabulary[1];
    const number = columns.find((column: string) => column !== kind);
    // Exactly two: the kind and the number, and nothing else. `food_standard`
    // (5) and `food_item_report_ingredient` (3, extending the product's own
    // key with a position) also close a key column's vocabulary, and picking
    // whichever the directory listed first would have made the owner - and so
    // the expected registry set - an accident of file names.
    if (columns.length !== 2 || !columns.includes(kind) || number === undefined) continue;
    owners.push({ file, cls: cls[1], kind, number });
  }
  return owners;
}

/** The derived table a registry column keys, and the two columns of its key. */
type Owner = { file: string; cls: string; kind: string; number: string };

/** The one such table, or none when the domain has none or cannot choose. */
function registryOwner(domain: string): Owner | undefined {
  const owners = registryOwners(domain);
  return owners.length === 1 ? owners[0] : undefined;
}
export function checkRelationsSync(): string[] {
  const issues: string[] = [];
  const domains = ledgerDomains();
  if (domains.length === 0) return issues;
  for (const domain of domains) issues.push(...checkDomain(domain));

  issues.push(...checkLedgersAreInTheirDomain(domains));

  const handJoin = HAND_JOIN_OF(domains);
  for (const layer of QUERY_LAYERS) {
    for (const file of layerFiles(join(APP_DIR, layer))) {
      const lines = readFileSync(join(APP_DIR, layer, file), "utf-8").split("\n");
      lines.forEach((line: string, index: number) => {
        if (handJoin.test(line)) {
          issues.push(
            `${layer}/${file}:${index + 1}: joins a domain model by its class — join along the ` +
              "relationship (`.outerjoin(FoodX.rel)`) so the edge is spelled once, on the model",
          );
        }
      });
    }
  }

  return issues;
}

/**
 * A ledger table's prefix is the folder it lives in.
 *
 * The domains are discovered from that agreement, so a ledger that breaks it
 * belongs to no domain and is checked by nothing — it declares relationships
 * freely and every gate stays green. Discovery must therefore report what it
 * could not place, never just skip it.
 */
function checkLedgersAreInTheirDomain(domains: string[]): string[] {
  const issues: string[] = [];
  for (const path of layerFiles(MODELS_DIR)) {
    const content = readFileSync(join(MODELS_DIR, path), "utf-8");
    const folder = path.includes("/") ? path.slice(0, path.indexOf("/")) : "";
    for (const match of content.matchAll(/__tablename__\s*=\s*"(\w+?)_ledger_(\w+)"/g)) {
      if (match[1] === folder) continue;
      issues.push(
        `models/${path}: ${match[1]}_ledger_${match[2]} is a ledger of the "${match[1]}" domain ` +
          `but sits in models/${folder === "" ? "" : `${folder}/`} — the domains are discovered ` +
          `from that agreement (found: ${domains.join(", ")}), so a ledger outside its own ` +
          "folder is checked by nothing at all",
      );
    }
  }
  return issues;
}

/** Every edge and every registry of one ledger domain. */
function checkDomain(domain: string): string[] {
  const ledgerDir = join(MODELS_DIR, domain);
  const issues: string[] = [];
  const LEDGER_TABLE = LEDGER_TABLE_OF(domain);
  const LEDGER_CLASS = LEDGER_CLASS_OF(domain);
  const owner = registryOwner(domain);

  for (const file of layerFiles(ledgerDir)) {
    const relative = `models/${domain}/${file}`;
    const content = readFileSync(join(ledgerDir, file), "utf-8");
    if (/\bForeignKey\(/.test(content)) {
      issues.push(
        `${relative}: declares a ForeignKey — ledgers are joined logically ` +
          "(a viewonly relationship with an explicit primaryjoin)",
      );
    }
    const isLedger = LEDGER_TABLE.test(content);
    for (const match of content.matchAll(RELATIONSHIP)) {
      const line = content.slice(0, match.index).split("\n").length;
      const name = match[1];
      const body = balanced(content, match.index + match[0].length - 1);
      const where = `${relative}:${line}: ${name}`;
      if (isLedger) {
        issues.push(
          `${where} is a relationship on a ledger — a ledger stores answers and states no ` +
            "question; declare the edge on the derived table that reads it",
        );
        continue;
      }
      if (LEDGER_CLASS.test(match[2])) {
        issues.push(
          `${where} points at a ledger model — an edge joins two derived tables; what a ` +
            "ledger holds reaches a derived table through its feed's pass, not through a join",
        );
        continue;
      }
      if (!/\bviewonly=True\b/.test(body)) {
        issues.push(`${where} is not viewonly=True — an edge into a ledger is read, never written through`);
      }
      if (!/\bprimaryjoin=/.test(body)) {
        issues.push(`${where} has no primaryjoin= — without a ForeignKey the edge must spell its columns`);
      } else if (!/\bforeign\(/.test(body)) {
        issues.push(`${where} primaryjoin marks no foreign(...) side — the mapper cannot tell the direction`);
      }
      if (/^list\[/.test(match[2]) && !/\buselist=True\b/.test(body)) {
        issues.push(
          `${where} is Mapped[list[...]] without uselist=True — with foreign() on the local side ` +
            "the mapper reads the edge as many-to-one and hands back one object",
        );
      }
      // The product is keyed by two columns, so an edge to it spells two.
      // `food_item_report` holds four registries that number in their own
      // spaces (rule://backend-ledger), so `item_report_no` alone names a row
      // of whichever registry got there first. Measured before the
      // rule: `food_barcode`, `food_label` and `food_nutrition` each joined on
      // the number alone, and 119,638 barcode rows resolved against a table
      // where the same number can belong to a 국내 report and a 축산물 one.
      if (owner !== undefined) {
        const edge = new RegExp(`\\b${owner.cls}\\s*\\.\\s*${owner.number}\\b`);
        if (edge.test(body) && !new RegExp(`\\b${owner.kind}\\b`).test(body)) {
          issues.push(
            `${where} joins the ${domain} product on ${owner.number} alone - its key is ` +
              `(${owner.kind}, ${owner.number}), and the registries number in separate ` +
              "spaces, so a number without its kind names whichever row was written first",
          );
        }
      }
      // An edge without a constraint is a claim about two tables' data, and the
      // claim is only as good as the count behind it: the comment above the
      // edge states what share resolves, dated. Measured before the rule: an edge
      // declared on a name (`FoodItemReportIngredient.raw_materials`) read as
      // "resolves" until the count said 18.5 %, and it was removed on that
      // number. Without the date, nobody can tell a fresh count from a stale one.
      const above = content.slice(0, match.index).split("\n").slice(-EVIDENCE_LINES).join("\n");
      if (!/#[^\n]*\b20\d\d-\d\d-\d\d\b/.test(above) || !/#[^\n]*\d/.test(above)) {
        issues.push(
          `${where} carries no dated measurement in the ${EVIDENCE_LINES} comment lines above it — ` +
            "an edge with no constraint is a claim about the data, and the claim is the count, " +
            "with the date it was taken (e.g. `# Measured 2026-09-09: 172,476 of 319,060 resolve`)", // history-ok: format example
        );
      }
    }
  }

  issues.push(...checkRegistriesAgree(domain));
  return issues;
}

/** `REGISTRIES` - the tuple a derivation declares its registries in. */
const REGISTRIES_DECL = /REGISTRIES[^=\n]*=\s*\(/;

/**
 * `async def _registry(self) -> dict[str, str]:` - the lookup, by its signature.
 *
 * The signature is the signal because neither looser one holds. The method
 * *name* alone matches `item_report_ingredient`, whose `_registry()` indexes
 * raw materials (I2520) and has nothing to do with which registry numbered a
 * report - it returns a `_Registry`, not a number→kind map. A line matching
 * `"report_kind": … registry` misses a resolver that puts the answer in a
 * local first. What every real one has is this: a map from a 품목제조보고번호
 * to the registry that numbers it.
 */
const REGISTRY_LOOKUP = /async def _registry\(self\)\s*->\s*dict\[str,\s*str\]:/;

/** `UNRESOLVED_REGISTRIES = {"FoodLedgerX": "why"}` - a registry left out on purpose. */
const UNRESOLVED_REGISTRIES = /UNRESOLVED_REGISTRIES[^=]*=\s*\{([\s\S]*?)\}/;

/** `NATURAL_KEY = ("report_kind", "item_report_no")` - a derived table's own key. */
const NATURAL_KEY = /NATURAL_KEY\s*[^=]*=\s*\(([^)]*)\)/;

/** `CheckConstraint("report_kind IN ('a', 'b')", …)` - a key column's closed vocabulary. */
const KEY_VOCABULARY = /CheckConstraint\(\s*\n?\s*"(\w+) IN \(/;

/**
 * Every derivation that resolves a product's registry reads every registry.
 *
 * `food_item_report` is keyed by (`report_kind`, `item_report_no`) and four
 * registries number in separate spaces, so a derivation holding a bare number
 * has to ask which registry it belongs to (`_registry()`). The lookup is only
 * as complete as the ledgers it reads, and an incomplete one does not fail - it
 * resolves to nothing.
 *
 * Measured: `safety_record` read two registries where its siblings read three.
 * Every 수거검사 of a 건강기능식품 - 18,536 records of 5,648 products - then
 * carried its number with no kind, and the read layer dropped them as naming no
 * product we hold. Every gate was green: each kind it *did* write was legal and
 * the edge was declared correctly.
 *
 * Three readings, each of which is a hole this closes:
 *
 * - **The truth is the owner's, not the siblings' agreement.** The expected set
 *   is every registry ledger `item_report.py` derives the table from, so three
 *   derivations forgetting the same new registry together still fails.
 * - **A lookup is found by its name, not by a constant.** Checking for a
 *   `REGISTRIES` tuple made the very shape the defect had - an inline
 *   `for … in ((A, x), (B, y)):` - invisible, so `_registry()` is what marks a
 *   resolving derivation and the tuple is what it must declare.
 * - **The tuple is read by balancing its parens**, not by a newline before the
 *   closing one: written on one line it used to match nothing, and a file that
 *   matches nothing is a file this check never looked at.
 *
 * A registry a derivation genuinely cannot resolve is a decision, and is
 * declared: `UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "why"}`.
 * 수입식품 numbers a product by a digest this codebase mints, so no published
 * record can carry one.
 */
function checkRegistriesAgree(domain: string): string[] {
  const issues: string[] = [];
  const servicesDir = join(APP_DIR, "services", domain);
  const modelsDir = join(MODELS_DIR, domain);
  if (!existsSync(servicesDir)) return issues;
  const LEDGER_TABLE = LEDGER_TABLE_OF(domain);
  const LEDGER_CLASS = LEDGER_CLASS_OF(domain);

  // Discovery that finds nothing must say so. This check reads the tree for
  // its own subject, and a subject it cannot find is indistinguishable from a
  // clean tree - the exact shape of the defect this check exists for. So a
  // domain that resolves registries while its owner cannot be found is a
  // finding, not a silence.
  const resolvers = layerFiles(servicesDir).filter((file: string) =>
    REGISTRY_LOOKUP.test(readFileSync(join(servicesDir, file), "utf-8")),
  );
  const candidates = registryOwners(domain);
  const owner = candidates.length === 1 ? candidates[0] : undefined;
  const ownerPath = owner === undefined ? "" : join(servicesDir, owner.file);
  if (owner === undefined || !existsSync(ownerPath)) {
    if (resolvers.length > 0) {
      issues.push(
        `services/${domain}/: ${resolvers.length} derivation(s) resolve a product's registry, but ` +
          (candidates.length === 0
            ? "no derived table in this domain is keyed by one — nothing to compare them against, " +
              "so this check would pass on anything. The owner is the model whose NATURAL_KEY is " +
              "(kind, number) with a CheckConstraint closing the kind"
            : `${candidates.length} tables are (${candidates
                .map((candidate: Owner) => candidate.file)
                .join(", ")}) — which one numbers the products cannot be guessed from the shape`),
      );
    }
    return issues;
  }

  // Every ledger the owner reads to build the table: those are the registries,
  // whatever any other derivation happens to remember.
  const anyLedger = new RegExp(LEDGER_CLASS.source, "g");
  const expected = new Set(
    [...readFileSync(ownerPath, "utf-8").matchAll(anyLedger)].map(
      (match: RegExpMatchArray) => match[0],
    ),
  );

  const ledgers = new Set<string>();
  for (const file of layerFiles(modelsDir)) {
    const content = readFileSync(join(modelsDir, file), "utf-8");
    if (!LEDGER_TABLE.test(content)) continue;
    for (const match of content.matchAll(new RegExp(`^class (${pascal(domain)}Ledger\\w+)\\(`, "gm"))) {
      ledgers.add(match[1]);
    }
  }

  for (const file of layerFiles(servicesDir)) {
    if (file === owner.file) continue;
    const content = readFileSync(join(servicesDir, file), "utf-8");
    if (!REGISTRY_LOOKUP.test(content)) continue;
    const label = `services/${domain}/${file}`;

    const declaration = REGISTRIES_DECL.exec(content);
    if (declaration === null) {
      issues.push(
        `${label}: resolves a product's registry with no REGISTRIES tuple - the ledgers a ` +
          "_registry() reads are the whole of what it can resolve, so they are named once, " +
          "where the next derivation and this check can both read them",
      );
      continue;
    }
    const tuple = balanced(content, declaration.index + declaration[0].length - 1);
    const resolved = new Set(
      [...tuple.matchAll(new RegExp(LEDGER_CLASS.source, "g"))].map(
        (match: RegExpMatchArray) => match[0],
      ),
    );
    const exemption = UNRESOLVED_REGISTRIES.exec(content);
    const declared = new Set(
      exemption === null
        ? []
        : [...exemption[1].matchAll(new RegExp(`"(${pascal(domain)}Ledger\\w+)"\\s*:`, "g"))].map(
            (match: RegExpMatchArray) => match[1],
          ),
    );

    const missing = [...expected].filter(
      (model: string) => !resolved.has(model) && !declared.has(model),
    );
    if (missing.length > 0) {
      issues.push(
        `${label}: REGISTRIES omits ${missing.join(", ")}, which ${owner.file} derives the ` +
          "product from - a number of that registry then carries no kind and the row resolves " +
          'to no product; name it, or declare it as UNRESOLVED_REGISTRIES = {"<model>": "why"}',
      );
    }
    for (const model of declared) {
      if (ledgers.has(model)) continue;
      issues.push(
        `${label}: UNRESOLVED_REGISTRIES declares ${model}, which no ledger model is - ` +
          "the reason answers nothing",
      );
    }
  }
  return issues;
}
