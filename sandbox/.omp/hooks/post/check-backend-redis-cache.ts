/**
 * Check-Backend-RedisCache Post Hook
 *
 * Validates backend-redis-cache.md: TTL reads, invalidation on writes, no auth-dependent caching
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { touchesPath } from "../lib/hook-scope.ts";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendRedisCache(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-redis-cache", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendRedisCacheSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-redis-cache");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-redis-cache",
      issues,
      "run make check-backend-redis-cache for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-redis-cache") };
  }));
}

function checkBackendRedisCacheSync(): string[] {
  const issues: string[] = [];

  const cachePath = join(appDir, "core", "cache.py");
  if (!existsSync(cachePath)) {
    return dormant("check-backend-redis-cache", "no app/core/cache.py");
  }

  // AST rules apply only to the optional cache module, not unrelated core code.
  const infraRules = join(projectRoot, ".omp", "ast-grep", "rules", "cache");
  if (existsSync(infraRules)) {
    issues.push(...runAstRules(infraRules, [cachePath]));
  }
  const cache = readFileSync(cachePath, "utf-8");

  // The repo's cache API is `ttl_seconds=` (backend-redis-cache.md); `ttl`
  // alone matched any identifier containing it, including `ttl_seconds` in a
  // comment.
  if (!/ttl_seconds/.test(cache)) {
    issues.push("cache.py: TTL required on cached reads");
  }
  // `del`/`delete` match half the standard library; the contract is an
  // invalidate() method on the cache.
  if (!/def invalidate\(|async def invalidate\(/.test(cache)) {
    issues.push("cache.py: invalidation on writes required");
  }

  const routersDir = join(appDir, "routers");
  if (existsSync(routersDir)) {
    for (const filename of readdirSync(routersDir)) {
      if (!filename.endsWith(".py")) continue;
      const router = readFileSync(join(routersDir, filename), "utf-8");
      if (!router.includes("CacheDep")) continue;
      if (!router.includes("scoped_cache_key(") || !router.includes("current_user.id")) {
        issues.push(
          `routers/${filename}: CacheDep requires scoped_cache_key(..., str(current_user.id), ...)`,
        );
      }
      issues.push(...checkCacheEndpoints(filename, router));
    }
  }
  // A pooled connection that died during a failover is handed to a request and
  // fails it — once per connection in the pool. The interval is what retires it.
  const mainPath = join(projectRoot, "backend", "app", "main.py");
  if (existsSync(mainPath)) {
    const main = readFileSync(mainPath, "utf-8");
    if (/Redis\.from_url\(/.test(main) && !/health_check_interval=/.test(main)) {
      issues.push(
        "main.py: Redis.from_url needs health_check_interval — a connection killed by a " +
          "failover otherwise fails one request per pooled connection",
      );
    }
  }

  return issues;
}

/**
 * Per endpoint, not per file: a cached read without a TTL never expires, and a
 * write that skips invalidation serves stale data until the TTL runs out. A
 * file-level substring check passes as long as one sibling endpoint does it.
 */
function checkCacheEndpoints(filename: string, router: string): string[] {
  const issues: string[] = [];
  const decorator = /@router\.(get|post|put|patch|delete)\(/g;
  const starts: Array<{ method: string; index: number }> = [];
  let match: RegExpExecArray | null;
  while ((match = decorator.exec(router)) !== null) {
    starts.push({ method: match[1], index: match.index });
  }
  for (let i = 0; i < starts.length; i++) {
    const end = i + 1 < starts.length ? starts[i + 1].index : router.length;
    const block = router.slice(starts[i].index, end);
    const method = starts[i].method;
    // Only endpoints that opted into the cache carry the dependency.
    if (!/cache:\s*CacheDep/.test(block)) continue;
    const signature = `${filename}:${method.toUpperCase()} endpoint`;
    if (method === "get") {
      if (!/ttl_seconds=/.test(block)) {
        issues.push(`routers/${signature}: cached read must set ttl_seconds= on set_json`);
      }
    } else if (!/cache\.invalidate\(/.test(block)) {
      issues.push(`routers/${signature}: write must call cache.invalidate() after the change`);
    }
  }
  return issues;
}

// Direct execution (make check-backend-redis-cache): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-redis-cache.ts")) {
  const issues = checkBackendRedisCacheSync();
  console.log("==> check-backend-redis-cache");
  if (issues.length === 0) {
    console.log(passLine("check-backend-redis-cache", "backend redis-cache standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-redis-cache");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
