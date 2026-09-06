// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * The ledgers of this repository, read off the provider jobs that fill them.
 *
 * A ledger is a table a batch job replaces with a whole pass of a provider
 * feed, and the fact lives in exactly one place: the `FEEDS` tuple of
 * `app/batch/sync_<provider>_ledgers.py`, one `Feed(<operation code>,
 * <Service>, <Service>.replace_<table>_ledger)` per ledger. Every check that
 * needs to know "is this table a ledger" — the read-only router, the ledger
 * list screen, the frontend domain shape — reads it from here rather than
 * from a file name, so a job may hold several ledgers and the name of the
 * job says which provider, not which table.
 *
 * Measured before this reader: the fact was the file name
 * (`sync_<domain>_<table>_ledger.py`, one job per table, retired 2026-09-06);
 * when the five jobs became two provider jobs, three checks stopped seeing any
 * ledger at once and demanded CRUD routers and form dialogs for every food
 * table.
 */
export interface LedgerFeed {
  /** The job module's stem, `sync_mfds_ledgers`. */
  job: string;
  /** `PROVIDER_CODE` of the job. */
  provider: string;
  /** The operation the feed walks, `search-barcode-item-info`. */
  operation: string;
  /** The service class the feed names, `FoodBarcodeService`. */
  service: string;
  /** The replacing method, `replace_barcode_ledger`. */
  replace: string;
  /** `app/services/<domain>/<table>.py` the service is imported from. */
  domain: string;
  table: string;
}

/** The job modules that fill ledgers: `app/batch/sync_*_ledgers.py`. */
export function ledgerJobFiles(backendApp: string): string[] {
  const batchDir = join(backendApp, "batch");
  if (!existsSync(batchDir)) return [];
  return readdirSync(batchDir)
    .filter((file: string) => /^sync_[a-z0-9_]+_ledgers\.py$/.test(file))
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
  for (const match of content.matchAll(/^from app\.services\.([a-z_]+)\.([a-z_]+) import (\w+)$/gm)) {
    imports.set(match[3], [match[1], match[2]]);
  }
  const feeds: LedgerFeed[] = [];
  for (const match of content.matchAll(
    /Feed\(\s*"([^"]+)",\s*(\w+),\s*(\w+)\.(replace_[a-z0-9_]+_ledger)\s*,?\s*\)/g,
  )) {
    const [domain, table] = imports.get(match[2]) ?? ["", ""];
    feeds.push({
      job,
      provider,
      operation: match[1],
      service: match[2],
      replace: match[4],
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
