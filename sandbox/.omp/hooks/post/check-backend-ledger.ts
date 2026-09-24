import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { layerFiles } from "../lib/backend-layout.ts";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join, relative } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { MUTATING_TOOLS } from "../lib/hook-mutating-tools.ts";
import { resolveProjectRoot } from "../lib/hook-project-root.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import {
  listIntegrationCallerInputs,
  listIntegrationOperationCodes,
  listIntegrationOperations,
  listIntegrationProviderCodes,
  listIntegrationResponseKeys,
} from "../lib/backend-migration-policy.ts";
import { feedsOf, listLedgerFeeds, type LedgerFeed } from "../lib/backend-ledger-feeds.ts";
import { listDerivations, type Derivation } from "../lib/backend-derivations.ts";

/**
 * Check-Backend-Ledger Post Hook
 *
 * After tool execution, validates the feed → ledger → derived chain of
 * .omp/rules/backend-ledger.md:
 *   1. A provider job (`sync_<provider>_ledgers.py`) states one provider, one
 *      window, one end code set, and a `FEEDS` tuple that ties every operation
 *      it walks to the `replace_<table>_ledger` of that table's service.
 *   2. Every code it names is a row some Alembic revision seeded, of that
 *      provider, and its feeds page by one family.
 *   3. Every ledger it fills reads every key its feed answers, and no other.
 *   4. A sync walks positions - a filter would import a subset.
 *   5. The reverse: every seeded operation that pages is a feed some provider
 *      job walks - an integration target is a ledger.
 *   6. Every derived table is a `Derivation` of some derive job, rebuilt by
 *      its own service; a derivation reads ledgers only and its rebuild has
 *      the one signature the job calls.
 *
 * The job shape itself (module = function = registry key = seeded row, steps,
 * knobs, the schedule table) is check-backend-batch.
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
const projectRoot = resolveProjectRoot();

export default function checkBackendLedger(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-ledger", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendLedgerSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-ledger");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-ledger",
      issues,
      "run make check-backend-ledger for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-ledger") };
  }));
}

function checkBackendLedgerSync(): string[] {
  const issues: string[] = [];
  const backendApp = join(projectRoot, "backend", "app");
  const batchDir = join(backendApp, "batch");
  if (!existsSync(batchDir)) return ["backend/app/batch/ directory not found"];

  for (const f of layerFiles(batchDir)) {
    if (f.includes("/") || f === "__init__.py") continue;
    const content = readFileSync(join(batchDir, f), "utf-8");
    const feeds = feedsOf(content, f.replace(/\.py$/, ""));

    // 1. A provider job states its provider, its window and its feeds.
    issues.push(...checkProviderJobShape(f, content, feeds));
    // 2. And the configuration it names exists in a migrated database.
    issues.push(...checkSeededConfiguration(f, feeds));
    // 3. And every ledger it fills reads every key its feed answers, through the wire types.
    for (const feed of feeds) {
      issues.push(...checkLedgerReadsTheContract(feed));
      issues.push(...checkLedgerValidatesThroughWireTypes(feed));
    }
    // 4. And it walks positions - a filter would import a subset.
    issues.push(...checkSyncWalksPositions(f, content, feeds));
  }

  // 5. Across every job: each seeded paging operation is somebody's feed.
  issues.push(...checkEveryPagingOperationIsAFeed());

  // 6. And each derived table is somebody's derivation, read off ledgers only.
  const derivations = listDerivations(backendApp);
  issues.push(...checkEveryDerivedTableIsRebuilt(derivations));
  issues.push(...checkDerivationContract(derivations));
  issues.push(...checkOneListSplitter());

  // 7. And no portal's own fact is a constant in the code that walks it.
  issues.push(...checkPortalFactsAreConfiguration(backendApp));

  return issues;
}

/**
 * A ledger job is `app/batch/sync_<table>.py`, and it holds one feed.
 *
 * One job, one ledger: the module's name is the table it fills
 * (`sync_food_ledger_recall` → `food_ledger_recall`), its `FEED` is the one
 * operation it walks, and its four constants say which provider, how wide a
 * window, what the portal answers past the last row, and who the rows say
 * wrote them. The walk itself is `sync_ledger`'s, where the pinned ledger
 * session, the steps and the failure live.
 *
 * The portal decided the shape. 식품안전나라 answers ERROR-503 to every service
 * and every key from 09:00 to 19:00 KST (measured), so a night is
 * fourteen hours and this provider's feeds are about eighteen - which no order
 * of one tuple fits. Separate jobs take separate nights. What the provider
 * still owns is its turn: the jobs of one provider are serialised by the
 * scheduler (`JOB_PROVIDERS`), one at a time.
 *
 * - The service a feed names is imported from `app.services.<domain>.<table>`,
 *   and the method it hands over is that table's `replace_<table>_ledger` -
 *   the only path through `LedgerStage`, whose floor refuses a pass that came
 *   back empty or lost half the ledger.
 * - The call passes the module's own constants, so a job cannot page or end
 *   differently from what its own header says.
 */
function checkProviderJobShape(file: string, content: string, feeds: LedgerFeed[]): string[] {
  const delegates = /\bsync_ledger\(/.test(content);
  const named = /^sync_[a-z0-9_]+\.py$/.test(file);
  if (!delegates && !named && feeds.length === 0) return [];
  const issues: string[] = [];
  const stem = file.replace(/\.py$/, "");

  if (feeds.length === 0) {
    issues.push(
      `app/batch/${file}: no FEED - a ledger job is one Feed(<operation>, <Service>, ` +
        "<Service>.replace_<table>_ledger), the ledger it fills",
    );
  }
  if (feeds.length > 1) {
    issues.push(
      `app/batch/${file}: names ${feeds.length} feeds - one job walks one feed, because a night ` +
        "holds one walk and the portal's night is fourteen hours",
    );
  }
  for (const [required, why] of [
    ["PROVIDER_CODE", "the provider a job reads is a seeded code, never a URL"],
    ["PAGE_SIZE", "the window this feed is walked at, measured"],
    ["END_CODES", "what the portal answers past its last row"],
    ["SYNCED_BY", "the rows say which job wrote them"],
  ] as const) {
    if (new RegExp(`^${required}\\s*(?::[^=]*)?=`, "m").test(content)) continue;
    issues.push(`app/batch/${file}: no ${required} - ${why}`);
  }
  // Read off the code, not the prose: the docstring names what the job refuses.
  const code = content.replace(/"""[\s\S]*?"""/g, "").replace(/#[^\n]*/g, "");
  for (const retired of ["MAX_PAGE_SIZE", "DEFAULT_MAX_", "total_count", "find_checkpoint"]) {
    if (!code.includes(retired)) continue;
    issues.push(
      `app/batch/${file}: mentions ${retired} - a pass is the whole feed every night; the ` +
        "floor in LedgerStage is the only guard, and there is no cursor, ceiling or count",
    );
  }
  // And the five names are *all* a job may declare. The blacklist above retires
  // the knobs this layer already had; a whitelist is what closes the class they
  // belong to - every fact about a service (its width, its quota codes, how its
  // feed is addressed) lives on the operation row, so a job with a sixth
  // constant is a portal fact that walked back into the code. Measured: the
  // coordinate arrived exactly that way, as a year on the path all 28 jobs
  // share, and nothing refused it.
  const OWNED = new Set(["PROVIDER_CODE", "PAGE_SIZE", "END_CODES", "SYNCED_BY", "FEED"]);
  for (const declaration of code.matchAll(/^([A-Z][A-Z0-9_]*)\s*(?::[^=\n]*)?=/gm)) {
    if (OWNED.has(declaration[1])) continue;
    issues.push(
      `app/batch/${file}: declares ${declaration[1]} - a ledger job owns five names ` +
        "(PROVIDER_CODE, PAGE_SIZE, END_CODES, SYNCED_BY, FEED); anything else it would " +
        "state about a service belongs on that service's integration_operation row, where " +
        "the walk reads it",
    );
  }

  for (const feed of feeds) {
    if (feed.table === "") {
      issues.push(
        `app/batch/${file}: ${feed.operation} names ${feed.service}, which is not imported from ` +
          "app.services.<domain>.<table> - the ledger a feed fills is a domain's table",
      );
      continue;
    }
    // The `ledger_` prefix is on the table because the table is one
    // (`food_ledger_nutrition`, rule://backend-relations); saying it again in the
    // method would read `replace_ledger_nutrition_ledger`.
    const replace = `replace_${feed.table.replace(/^ledger_/, "")}_ledger`;
    if (feed.replace !== replace) {
      issues.push(
        `app/batch/${file}: ${feed.operation} replaces through ${feed.service}.${feed.replace}, ` +
          `but ${feed.service} is app/services/${feed.domain}/${feed.table}.py - the method is ` +
          `${replace}, the one path through LedgerStage and its floor`,
      );
    }
    const expected = `sync_${feed.domain}_${feed.table}`;
    if (stem !== expected) {
      issues.push(
        `app/batch/${file}: fills ${feed.domain}_${feed.table} but is called '${stem}' - a ledger ` +
          `job is named after the ledger it owns, so this file is app/batch/${expected}.py`,
      );
    }
    if (!new RegExp(`^SYNCED_BY\\s*=\\s*"batch:${expected}"`, "m").test(content)) {
      issues.push(
        `app/batch/${file}: SYNCED_BY does not read "batch:${expected}" - the rows of a ledger ` +
          "name the job that wrote them, and the job is named after the ledger",
      );
    }
  }

  if (!delegates && feeds.length > 0) {
    issues.push(
      `app/batch/${file}: does not call sync_ledger - the walk, the pinned ledger session, the ` +
        "step per window and the failure are one body every ledger job shares",
    );
  }
  for (const call of content.matchAll(/sync_ledger\(([\s\S]*?)\n\s*\)/g)) {
    for (const [what, constant] of [
      ["the provider", "PROVIDER_CODE"],
      ["its feed", "FEED"],
      ["its actor", "SYNCED_BY"],
      ["its window", "page_size=PAGE_SIZE"],
      ["its end rule", "end_codes=END_CODES"],
    ] as const) {
      if (call[1].includes(constant)) continue;
      issues.push(
        `app/batch/${file}: the sync_ledger call does not pass ${constant} - ${what} is the ` +
          "module's own constant, so the header and the walk cannot disagree",
      );
    }
  }
  return issues;
}


/**
 * The provider and every operation a job names must be rows a revision inserts,
 * and the operations must page the same way.
 *
 * `PROVIDER_CODE` and each feed's operation are strings resolved at 03:00
 * against `integration_provider` / `integration_operation`. Nothing else in the
 * stack connects them: the job type-checks, its tests script the seam and never
 * look the codes up, and every gate stays green - measured, by pointing a job at
 * `search-ghost-material` and running the whole suite. The failure surfaces once
 * a night, in a scheduler log, as configuration that does not exist.
 *
 * The family is a provider fact too: the job asks every feed for windows of
 * `PAGE_SIZE` and reads the end the same way, which only holds when the feeds
 * page by the same keys. A feed of the other family in the tuple would be
 * asked for `range_start` by a walk that sends `page_no`.
 *
 * Read from the migrations rather than the database, so a fresh clone answers
 * the same as the machine that already ran `migrate`.
 */
function checkSeededConfiguration(file: string, feeds: LedgerFeed[]): string[] {
  if (feeds.length === 0) return [];
  const issues: string[] = [];
  const providers = listIntegrationProviderCodes();
  const operations = listIntegrationOperationCodes();
  const inputs = listIntegrationCallerInputs();

  const [{ provider }] = feeds;
  if (provider !== "" && !providers.includes(provider)) {
    issues.push(
      `app/batch/${file}: PROVIDER_CODE '${provider}' is seeded by no migration - a job whose ` +
        "integration_provider row does not exist runs once a night and fails on " +
        `configuration, not on data (seeded: ${providers.join(", ") || "none"})`,
    );
  }
  const families = new Map<string, string>();
  const seededOperations = listIntegrationOperations();
  const providerOf = new Map(seededOperations.map((op) => [op.code, op.provider]));
  // A file door (response_format CSV) is one request for the whole feed, read
  // in chunks of page_size: it has no window to widen and is walked anyway.
  const formatOf = new Map(seededOperations.map((op) => [op.code, op.format]));
  for (const feed of feeds) {
    if (!operations.includes(feed.operation)) {
      issues.push(
        `app/batch/${file}: feed '${feed.operation}' is seeded by no migration - a job whose ` +
          "integration_operation row does not exist runs once a night and fails on " +
          `configuration, not on data (seeded: ${operations.join(", ") || "none"})`,
      );
      continue;
    }
    const owner = providerOf.get(feed.operation) ?? null;
    if (owner !== null && provider !== "" && owner !== provider) {
      issues.push(
        `app/batch/${file}: feed '${feed.operation}' is an operation of '${owner}', not of ` +
          `'${provider}' - the walk resolves (provider, operation) as a pair, and a job ` +
          "walks its own provider's feeds",
      );
    }
    const keys = inputs.get(feed.operation) ?? [];
    const family = formatOf.get(feed.operation) === "CSV"
      ? "FILE"
      : keys.includes("range_start") ? "RANGE" : keys.includes("page_no") ? "PAGE" : "none";
    families.set(feed.operation, family);
  }
  const distinct = new Set(families.values());
  if (distinct.size > 1) {
    const listed = [...families].map(([operation, family]) => `${operation}=${family}`).join(", ");
    issues.push(
      `app/batch/${file}: its feeds page by different families (${listed}) - one provider job ` +
        "asks every feed for the same window, so a feed of another family belongs to another job",
    );
  }
  if (distinct.has("none")) {
    const unpaged = [...families].filter(([, family]) => family === "none").map(([op]) => op);
    issues.push(
      `app/batch/${file}: ${unpaged.join(", ")} seeds no paging keys (range_start or page_no) - ` +
        "a feed a walk cannot window is not a feed",
    );
  }
  return issues;
}

/**
 * A ledger's `from_record` and its feed's seeded record keys agree, both ways.
 *
 * The mapping is a list of `record.get("<key>")` calls, and nothing types it:
 * `record` is a `Mapping[str, object]`, so a misspelt key reads `None`, the
 * column is stored NULL on every record forever, and the run reports success.
 * The reverse drift is quieter still - a key added to the seed that the ledger
 * never reads is simply data the sync drops.
 *
 * A key the ledger declines on purpose (`row_no`, the record's position inside
 * its page) is declared in an `UNSTORED_KEYS` set beside `from_record`, with
 * the reason, so the decline is a decision the check can read rather than an
 * omission it cannot tell from a mistake.
 *
 * Per feed: the schema is `app/schemas/<domain>/<table>.py`, the service's
 * sibling, and the keys are the ones the feed's operation answers.
 */
function checkLedgerReadsTheContract(feed: LedgerFeed): string[] {
  if (feed.table === "") return [];
  const seeded = listIntegrationResponseKeys().get(feed.operation);
  const schemaPath = join(projectRoot, "backend", "app", "schemas", feed.domain, `${feed.table}.py`);
  if (!existsSync(schemaPath)) return [];
  const schema = readFileSync(schemaPath, "utf-8");
  const label = `app/schemas/${feed.domain}/${feed.table}.py`;
  const issues: string[] = [];
  if (seeded === undefined || seeded.length === 0) {
    // A walked feed whose seed reads as answering nothing is the reader's
    // defect, not a pass: measured on the first screen feed, whose selectors
    // matched no pointer pattern, so every key it read went unchecked.
    return [
      `${label}: the field seed of ${feed.operation} reads as answering no RESPONSE rows - ` +
        "a walked feed has columns, so the seed's RESPONSE_ROWS or the reader is wrong",
    ];
  }

  const read = new Set([...schema.matchAll(/record\.get\("([a-z0-9_]+)"\)/g)].map((m) => m[1]));
  const unstored = new Set(
    [...(/^UNSTORED_KEYS\s*=\s*frozenset\(\{([^}]*)\}\)/m.exec(schema)?.[1] ?? "").matchAll(/"([a-z0-9_]+)"/g)]
      .map((m) => m[1]),
  );
  for (const key of read) {
    if (seeded.includes(key)) continue;
    issues.push(
      `${label}: from_record reads "${key}", which ${feed.operation} never answers - the column ` +
        "is NULL on every record and the sync reports success",
    );
  }
  for (const key of seeded) {
    if (read.has(key) || unstored.has(key)) continue;
    issues.push(
      `${label}: ${feed.operation} answers "${key}" and the ledger neither stores it nor declines ` +
        "it in UNSTORED_KEYS - data dropped on the floor, or a column that was never added",
    );
  }
  return issues;
}

/**
 * A ledger's `from_record` hands the raw record to `model_validate`; the field
 * types do the reading.
 *
 * Eleven ledgers once wrapped every column in `source_text(record.get(...))` -
 * two hundred calls to a helper that laundered `object` into `str | None` for
 * the type checker and normalised nothing the type could not. The wire dialect
 * is a set of `Annotated` types in `schemas/<provider>.py` (`MfdsText`,
 * `MfdsDatetime`), the mutable model extends the provider's record base, and
 * `from_record` builds through `model_validate` so a raw `record.get("key")`
 * reaches a typed field. A schema that wraps or calls a public parse helper is
 * a second dialect beside the first, and the two drift a timezone apart.
 */
function checkLedgerValidatesThroughWireTypes(feed: LedgerFeed): string[] {
  if (feed.table === "") return [];
  const schemaPath = join(projectRoot, "backend", "app", "schemas", feed.domain, `${feed.table}.py`);
  if (!existsSync(schemaPath)) return []; // existence-ok: the contract check reports the missing schema
  const schema = readFileSync(schemaPath, "utf-8");
  const label = `app/schemas/${feed.domain}/${feed.table}.py`;
  const issues: string[] = [];
  const fromRecord = /def from_record\([\s\S]*?(?=\n    (?:@|def )|\nclass |\n\n\n|\s*$)/.exec(schema)?.[0] ?? "";
  if (fromRecord === "") return [`${label}: no from_record - a ledger schema validates one provider record`];
  if (!/\bcls\.model_validate\(/.test(fromRecord)) {
    issues.push(
      `${label}: from_record does not build through cls.model_validate - a raw record.get() reaches ` +
        "a typed field there; a constructor call needs every value pre-parsed by hand",
    );
  }
  for (const call of fromRecord.matchAll(/(?<!cls\.)\b(\w+)\(\s*record\.get\(/g)) {
    // A module-private helper for one column's own oddity (`_amount`, thousands
    // separators in a numeric field) and the record base's own key guard
    // (`cls.key_text`) are the two readers a column may pass through.
    if (/^_/.test(call[1])) continue;
    issues.push(
      `${label}: from_record wraps record.get() in ${call[1]}() - the wire dialect is the field's ` +
        "Annotated type (schemas/<provider>.py), not a helper called per column",
    );
  }
  return issues;
}

/**
 * A pass walks positions; it never sends a filter.
 *
 * Every operation here seeds optional caller inputs beside its paging keys -
 * `change_date`, `changed_from`, `last_updated_from`, `update_date`, a product
 * name, a licence number. Each reads a *subset*, and a subset is not a ledger:
 * a job that sent `change_date` would import what changed since a date and
 * call the ledger whole. The temptation is real - measured on
 * `search-food-item-report`, the unfiltered walk is capped at 100 calls an hour
 * (`INFO-320`) and the date filter is not - and the answer is to pay the quota
 * in hours, which the walk's quota wait exists for.
 *
 * So the window a walk sends holds the paging family's keys and nothing the
 * seed lists as a caller input. Read as dict-key syntax (`"key":`), because the
 * job's docstring names the filters it refuses.
 */
function checkSyncWalksPositions(file: string, content: string, feeds: LedgerFeed[]): string[] {
  const paging = new Set(["range_start", "range_end", "page_no", "num_of_rows"]);
  const issues: string[] = [];
  const inputs = listIntegrationCallerInputs();
  for (const feed of feeds) {
    for (const key of inputs.get(feed.operation) ?? []) {
      if (paging.has(key)) continue;
      // The segment this feed declares is walked over *every* value it has, so
      // the union is the feed: a coordinate, not a subset (rule://backend-ledger).
      if (key === feed.segment) continue;
      if (!new RegExp(`"${key}"\\s*:`).test(content)) continue;
      issues.push(
        `app/batch/${file}: sends "${key}" to ${feed.operation} - a filter reads a subset, and a ` +
          "ledger is everything; a pass is windows of PAGE_SIZE from row 1, never a date",
      );
    }
  }
  return issues;
}

/**
 * Every seeded operation that pages is a feed of its provider's job.
 *
 * The forward checks read a job and ask whether what it names exists; this
 * one reads the seeds and asks whether what exists is walked. Without it, an
 * integration is "done" the moment its configuration is seeded and its
 * fixture recorded - and a paging operation nobody walks is a feed the
 * database never holds, which is the whole point of seeding one. Measured
 * on this tree: `search-product-classification` and `search-test-item` were
 * seeded (revision 64) and configured, and no job read either for the whole
 * life of the five-jobs design.
 *
 * Paging is the criterion, not existence: an operation without a window
 * (`range_start`/`page_no` absent from its caller inputs) is a lookup the API
 * answers per call, and a lookup has no feed to replace a ledger with. A file
 * (`response_format` CSV) is the whole feed in one answer, so it is a feed
 * by the same reasoning without carrying a window.
 */
function checkEveryPagingOperationIsAFeed(): string[] {
  const issues: string[] = [];
  const backendApp = join(projectRoot, "backend", "app");
  const feeds = listLedgerFeeds(backendApp);
  const walked = new Set(feeds.map((feed) => feed.operation));
  const jobOf = new Map(feeds.map((feed) => [feed.provider, feed.job]));
  const inputs = listIntegrationCallerInputs();
  for (const operation of listIntegrationOperations()) {
    if (!operation.configured || walked.has(operation.code)) continue;
    const keys = inputs.get(operation.code) ?? [];
    const isFile = operation.format === "CSV";
    if (!isFile && !keys.includes("range_start") && !keys.includes("page_no")) continue;
    const provider = operation.provider ?? "its provider";
    const job = jobOf.get(provider) ?? `sync_${provider.replace(/-/g, "_")}_ledgers`;
    issues.push(
      `app/batch/${job}.py: seeded operation '${operation.code}' (${provider}) ${isFile ? "is a file" : "pages"} but no Feed ` +
        "walks it - an integration target is a ledger: build the table and its " +
        "`replace_<table>_ledger` (the `ledger` skill), then add " +
        `Feed("${operation.code}", <Table>Service, <Table>Service.replace_<table>_ledger) ` +
        `to FEEDS${jobOf.has(provider) ? "" : " of a new provider job"}`,
    );
  }
  return issues;
}

/**
 * Every derived table is rebuilt by some derive job, and by its own service.
 *
 * A derived table (`food_*` under `models/food/` without the ledger prefix,
 * rule://backend-relations) is a function of the ledgers that nothing but the
 * derive job writes: one nobody rebuilds is empty forever, and every screen
 * that reads it is green on nothing. Measured on the tree this check landed
 * on: four derived tables, and for the hours between their models and the
 * derive job they were exactly that - empty, with every other gate passing.
 *
 * The shape held: `Derivation(<Svc>, <Svc>.rebuild_<table>)` in an
 * `app/batch/derive_*.py`, `<Svc>` imported from `app.services.food.<table>`,
 * the same chain a `Feed` walks (`hooks/lib/backend-ledger-feeds.ts`).
 */
function checkEveryDerivedTableIsRebuilt(derivations: Derivation[]): string[] {
  const issues: string[] = [];
  const rebuilt = new Set<string>();
  const domains = new Set<string>();
  for (const d of derivations) {
    if (d.table === "" || d.owner !== d.service || d.rebuild !== `rebuild_${d.table}`) {
      issues.push(
        `app/batch/${d.job}.py: Derivation(${d.service}, ${d.owner}.${d.rebuild}) - a derivation rebuilds ` +
          "its own table through its own service: Derivation(<Svc>, <Svc>.rebuild_<table>) " +
          "with <Svc> imported from app.services.<domain>.<table>",
      );
      continue;
    }
    for (const table of d.tables) rebuilt.add(`${d.domain}/${table}`);
    domains.add(d.domain);
  }

  // Every model beside a ledger in a domain that derives is a derived table.
  for (const domain of domains) {
    const modelsDir = join(projectRoot, "backend", "app", "models", domain);
    if (!existsSync(modelsDir)) continue; // existence-ok: the service import that named the domain fails check-backend-domain
    for (const file of layerFiles(modelsDir)) {
      if (file.includes("/") || file.startsWith("ledger_")) continue;
      const table = file.replace(/\.py$/, "");
      const content = readFileSync(join(modelsDir, file), "utf-8");
      if (!/__tablename__\s*=/.test(content) || rebuilt.has(`${domain}/${table}`)) continue;
      issues.push(
        `app/models/${domain}/${file}: derived table '${domain}_${table}' is rebuilt by no derive job - a ` +
          "derived table is a function of the ledgers and the derive job is its only writer; add " +
          `Derivation(<Svc>, <Svc>.rebuild_${table}) to DERIVATIONS of app/batch/derive_*.py`,
      );
    }
  }
  return issues;
}

/**
 * A derivation reads ledgers only, and its rebuild has the one signature.
 *
 * `DERIVATIONS` is ordered so that a *reader* of the graph finds every edge's
 * target rebuilt no later than its source; it is not a write-time dependency.
 * A derivation that scanned another derived table would make it one - correct
 * only while the tuple stays in that order, and empty the night it is
 * reordered, with every gate green. Read off the imports, not the call sites:
 * a `scan_table(` call names a loop variable as easily as a class (measured on
 * the ingredient split, `for kind, ledger in SOURCES`), and the import list
 * cannot. A derived service imports from `app.models.food` its own model
 * module and `ledger_*` modules, nothing else.
 *
 * And the registry calls `rebuild_<table>(synced_by)` by name: a service whose
 * method is spelled otherwise, or takes another argument, fails at 10:00 in
 * the executor and nowhere else.
 */
/**
 * One splitter for every joined list.
 *
 * Four registries punctuate their 원재료 lists differently - `()` everywhere,
 * `{}`/`[]`/`<>` on the 건강기능식품 lists, a thousands comma inside a quantity -
 * and a second splitter is a second answer to "what did this registry list".
 * Measured: the ingredient service counted depth over `()` alone and
 * cut 유산균{... 100,000,000,000개/g 이상, 희석제(옥수수전분) 적량} into four
 * fragments, while `core/printed_label` counted six bracket kinds for the same
 * paragraphs - one repository, two readings.
 *
 * So the depth-counting loop lives in `core/printed_label.split_list` and
 * nowhere else: a `.split(",")` or a hand-written bracket counter anywhere under
 * `app/` is the second answer coming back.
 */
function checkOneListSplitter(): string[] {
  const issues: string[] = [];
  const appDir = join(projectRoot, "backend", "app");
  if (!existsSync(appDir)) return issues;
  const owner = join("core", "printed_label.py");
  const walk = (dir: string): string[] => {
    const found: string[] = [];
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "__pycache__") continue;
      const path = join(dir, entry.name);
      if (entry.isDirectory()) found.push(...walk(path));
      else if (entry.name.endsWith(".py")) found.push(path);
    }
    return found;
  };
  for (const path of walk(appDir)) {
    const label = relative(appDir, path);
    if (label === owner) continue;
    const content = readFileSync(path, "utf-8");
    const code = content
      .split("\n")
      .map((line: string) => (/^\s*#/.test(line) ? "" : line));
    // A bracket walk alone is not a splitter - `_balanced` reads how far a name's
    // brackets close and splits nothing. What this refuses is a *separator* read
    // at depth zero, and a bare `.split(",")` over a provider's list.
    const separatorAtDepthZero =
      /depth\s*(?:\+=|-=|=\s*max\()/.test(code.join("\n")) &&
      /depth\s*==\s*0/.test(code.join("\n"));
    for (const [index, line] of code.entries()) {
      const splitsOnComma = /\.split\(\s*["'](?:,|，)["']\s*\)/.test(line);
      // The line must read a *separator* at depth zero, not merely mention the
      // depth: `return name if depth == 0 else ...` closes a bracket walk.
      const separator =
        separatorAtDepthZero &&
        /depth\s*==\s*0/.test(line) &&
        /(?:\bin\s+\w+|["'](?:,|，)["'])/.test(line);
      if (!splitsOnComma && !separator) continue;
      issues.push(
        `app/${label}:${index + 1}: splits a joined list by hand - every list is split by ` +
          "core.printed_label.split_list, which counts depth over every bracket pair the " +
          "registries use and leaves a thousands comma alone",
      );
    }
  }
  return issues;
}

/**
 * A portal's own fact is configuration, never a constant in the code that walks it.
 *
 * Width, end codes and quota waits already live on the `integration_operation`
 * row; the last fact that did not was *how a feed is addressed*. One batch
 * module held `FIRST_SEGMENT_YEAR = 2016` - a fact about three 생산실적 services -
 * on the path all 28 jobs share, and `Feed` carried a `segment_key` that 25 jobs
 * passed as None. Neither the year nor the coordinate is knowledge the walking
 * code can have: the next provider splits its feed by something else, or by
 * nothing.
 *
 * Two shapes are refused, and both were the real ones:
 *
 * - a four-digit year used as a boundary anywhere under `app/batch/` or
 *   `app/services/batch/` - the constant this move deleted;
 * - a `Feed(...)` with more than the three elements a job owns (its operation,
 *   its service, its replace) - the tuple element this move deleted.
 *
 * Why it matters more than tidiness: a coordinate that goes missing does not
 * fail, it walks. The same feed read flat costs the square of its windows -
 * measured inside one year of I0300, 0.92 s per window at offset 0
 * against 6.36 s past 1,000,000, which is ~6 h year by year against ~48 h flat.
 */
function checkPortalFactsAreConfiguration(backendApp: string): string[] {
  const issues: string[] = [];
  // Every other domain's services are free to hold a year; only the code that asks
  // a portal is not - and these are the two directories that code lives in.
  // domain-literal: 'batch' names those directories, not a business domain.
  const dirs = [join(backendApp, "batch"), join(backendApp, "services", "batch")];
  for (const dir of dirs) {
    if (!existsSync(dir)) continue;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isFile() || !entry.name.endsWith(".py")) continue;
      const path = join(dir, entry.name);
      const label = `app/${relative(backendApp, path)}`;
      const lines = readFileSync(path, "utf-8").split("\n");
      // Prose may name a year - a measurement is dated, and a docstring is where
      // this codebase keeps its measurements. Code may not hold one.
      let inDocstring = false;
      for (const [index, line] of lines.entries()) {
        const fences = (line.match(/"""/g) ?? []).length;
        const wasInDocstring = inDocstring;
        if (fences % 2 === 1) inDocstring = !inDocstring;
        if (wasInDocstring || inDocstring) continue;
        const code = line.replace(/#.*$/, "");
        if (!/(?:^|[^\w."'])(?:19|20)\d{2}(?![\w."'%-])/.test(code)) continue;
        issues.push(
          `${label}:${index + 1}: a calendar year in the code that walks a feed - which ` +
            "coordinate a service is published by, and the oldest one worth asking for, are " +
            "facts about that service: they belong on its integration_operation row " +
            "(segment_key / segment_values), beside its page_size and quota_codes",
        );
      }
      const content = lines.join("\n");
      for (const feed of content.matchAll(/Feed\(([^)]*)\)/g)) {
        const elements = feed[1].split(",").map((e: string) => e.trim()).filter(Boolean);
        if (elements.length <= 3) continue;
        issues.push(
          `${label}: Feed(...) carries ${elements.length} elements - a job owns its operation, ` +
            "its service and its replace, and nothing else; how the feed is addressed is " +
            "configuration the walk reads from the operation row",
        );
      }
    }
  }
  return issues;
}

function checkDerivationContract(derivations: Derivation[]): string[] {
  const issues: string[] = [];
  for (const d of derivations) {
    if (d.table === "") continue; // reported by checkEveryDerivedTableIsRebuilt
    const path = join(projectRoot, "backend", "app", "services", d.domain, `${d.table}.py`);
    if (!existsSync(path)) continue; // existence-ok: the import that named it fails check-backend-domain
    const content = readFileSync(path, "utf-8");
    const label = `app/services/${d.domain}/${d.table}.py`;

    const models = new RegExp(`^from app\\.models\\.${d.domain}(?:\\.([a-z0-9_]+))? import ([^\\n]+)`, "gm");
    for (const hit of content.matchAll(models)) {
      const modules = hit[1] !== undefined ? [hit[1]] : hit[2].split(",").map((m: string) => m.trim().split(/\s+as\s+/)[0]);
      for (const module of modules) {
        if (module === d.table || d.tables.includes(module) || module.startsWith("ledger_")) continue;
        issues.push(
          `${label}: imports app.models.${d.domain}.${module} - a derivation is a function of the ledgers, ` +
            "and one that reads another derived table depends on the write order of DERIVATIONS, " +
            "which promises a read order only",
        );
      }
    }

    const signature = new RegExp(`^    async def ${d.rebuild}\\(self, synced_by: str\\) -> int:`, "m");
    if (!signature.test(content)) {
      issues.push(
        `${label}: no \`async def ${d.rebuild}(self, synced_by: str) -> int\` - the derive job calls ` +
          "every rebuild the same way, and a method spelled otherwise fails in the executor",
      );
    }
  }
  return issues;
}

// Direct execution (make check-backend-ledger): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-ledger.ts")) {
  const issues = checkBackendLedgerSync();
  console.log("==> check-backend-ledger");
  if (issues.length === 0) {
    console.log("    PASS: every feed syncs its ledger through the stage, and every derived table is a derivation");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-ledger");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
