// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * The ledgers of this repository, read off the provider jobs that fill them.
 *
 * A ledger is a table a batch job replaces with a whole pass of a provider
 * feed, and the fact lives in exactly one place: the `FEED` of
 * `app/batch/sync_<table>.py`. Every check that needs to know "is this table a
 * ledger" — the read-only router, the ledger list screen, the frontend domain
 * shape — reads it from here rather than from a file name.
 *
 * The shape has been both ways, and the portal decided it: one job per table
 * (retired for its cursors) became two provider jobs, and those
 * became one job per ledger again when 식품안전나라 was measured
 * shut 09:00-19:00 KST — eighteen hours of walking does not fit a fourteen
 * hour night in any order, so the feeds are laid across several nights as
 * separate schedule rows. What is kept from the provider-job design is this
 * reader: the fact is the `Feed(...)` in the module, never the file name.
 */
export interface LedgerFeed {
  /** The job module's stem, `sync_mfds_ledgers`. */
  job: string;
  /** `PROVIDER_CODE` of the job. */
  provider: string;
  /** The operation the feed walks, `search-food-raw-material`. */
  operation: string;
  /** The service class the feed names, `FoodRawMaterialService`. */
  service: string;
  /** The replacing method, `replace_raw_material_ledger`. */
  replace: string;
  /** The caller input the feed is addressed by, `report_year`, or "". */
  segment: string;
  /** `app/services/<domain>/<table>.py` the service is imported from. */
  domain: string;
  table: string;
}

/** The job modules that fill ledgers: `app/batch/sync_*_ledgers.py`. */
export function ledgerJobFiles(backendApp: string): string[] {
  const batchDir = join(backendApp, "batch");
  if (!existsSync(batchDir)) return [];
  return readdirSync(batchDir)
    .filter((file: string) => /^sync_[a-z0-9_]+\.py$/.test(file))
    .sort();
}

/**
 * Every feed of one job module, as its `FEEDS` tuple and imports declare them.
 *
 * A `Feed(...)` whose service is imported from somewhere other than
 * `app.services.<domain>.<table>` is still returned, with empty `domain` and
 * `table`: the batch check reports it, and a reader asking for ledger tables
 * simply does not see it.
 */
export function feedsOf(content: string, job: string): LedgerFeed[] {
  const provider = /^PROVIDER_CODE\s*=\s*"([^"]+)"/m.exec(content)?.[1] ?? "";
  const imports = new Map<string, [string, string]>();
  // One name per line, or the parenthesised form the formatter folds a long
  // module path into - both bind the same service to the same table.
  for (const match of content.matchAll(
    /^from app\.services\.([a-z_]+)\.([a-z_]+) import (?:(\w+)|\(\s*([\w\s,]+?)\s*,?\s*\))$/gm,
  )) {
    for (const name of (match[3] ?? match[4]).split(/[\s,]+/).filter(Boolean)) {
      imports.set(name, [match[1], match[2]]);
    }
  }
  const feeds: LedgerFeed[] = [];
  for (const match of content.matchAll(
    /Feed\(\s*"([^"]+)",\s*(\w+),\s*(\w+)\.(replace_[a-z0-9_]+_ledger)\s*,?\s*(?:"([a-z0-9_]+)"\s*,?\s*)?\)/g,
  )) {
    const [domain, table] = imports.get(match[2]) ?? ["", ""];
    feeds.push({
      job,
      provider,
      operation: match[1],
      service: match[2],
      replace: match[4],
      segment: match[5] ?? "",
      domain,
      table,
    });
  }
  return feeds;
}

/** Every feed of every provider job under `backend/app`. */
export function listLedgerFeeds(backendApp: string): LedgerFeed[] {
  const feeds: LedgerFeed[] = [];
  for (const file of ledgerJobFiles(backendApp)) {
    const content = readFileSync(join(backendApp, "batch", file), "utf-8");
    feeds.push(...feedsOf(content, file.replace(/\.py$/, "")));
  }
  return feeds;
}

/** The tables of one domain some feed replaces — `[]` for a domain people edit. */
export function ledgerTablesOf(backendApp: string, domain: string): string[] {
  return listLedgerFeeds(backendApp)
    .filter((feed) => feed.domain === domain)
    .map((feed) => feed.table);
}
