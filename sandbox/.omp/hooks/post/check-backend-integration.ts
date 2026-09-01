/**
 * Check-Backend-Integration Post Hook
 *
 * After tool execution, validates the transport contract shared by every
 * database-managed external integration:
 *   1. IntegrationClient resolves a configured operation and executes it
 *   2. httpx2.AsyncClient used (never sync requests)
 *   3. Per-operation timeout and bounded retry behavior
 *   4. Integration error mapping and shared client lifecycle
 *
 * This is a read-only check — it does NOT block tool calls.
 * Log issues for the user to address.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { listDomainLayerFiles } from "../lib/backend-domain-structure.ts";
import { touchesPath } from "../lib/hook-scope.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";
import { FILE_EDIT_TOOLS } from "../lib/hook-mutating-tools.ts";

const cwd = process.cwd();
// Adjust cwd to project root if running from backend/
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

/**
 * Read-only tools never change files — running the check after them wastes
 * context. Only run after tools that can modify the workspace.
 */
const MUTATING_TOOLS = new Set([
  ...FILE_EDIT_TOOLS, "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendIntegration(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-integration", event, () => {
    // Skip read-only tools — they cannot change integration files.
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;
    if (!touchesPath(event, ["backend/"])) return;

    const issues = checkBackendIntegrationSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-integration"); // resolved — allow re-warning on new violations
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-integration",
      issues,
      "run make check-backend-integration for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-integration") };
  }));
}

function checkBackendIntegrationSync(): string[] {
  const issues: string[] = [];
  const integrationPath = join(appDir, "core", "integration.py");
  const exceptionsPath = join(appDir, "core", "exceptions.py");
  const depsPath = join(appDir, "dependencies", "integrations.py");
  const mainPath = join(appDir, "main.py");

  // --- 1. IntegrationClient base class ---
  if (!existsSync(integrationPath)) {
    // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
    issues.push("app/core/integration.py not found — IntegrationClient base class required");
    return issues;
  }
  const integration = readFileSync(integrationPath, "utf-8");

  if (!/class IntegrationClient/.test(integration)) {
    issues.push("integration.py: IntegrationClient class required");
  }
  if (!/async def execute\(/.test(integration)) {
    issues.push("integration.py: async execute() method required");
  }
  if (!/async def from_database\(/.test(integration)) {
    issues.push("integration.py: from_database() configuration resolver required");
  }
  if (!/async def _backoff\(/.test(integration)) {
    issues.push("integration.py: async _backoff() retry method required");
  }
  if (!/def _retry_after\(/.test(integration)) {
    issues.push("integration.py: _retry_after() Retry-After parser required");
  }
  if (!/async def aclose\(/.test(integration)) {
    issues.push("integration.py: async aclose() lifecycle method required");
  }

  // --- 2. httpx2.AsyncClient only (never sync requests) ---
  if (!/httpx2\.AsyncClient/.test(integration)) {
    issues.push("integration.py: must use httpx2.AsyncClient (async only)");
  }
  if (/\brequests\.(get|post|put|delete|patch)\b/.test(integration)) {
    issues.push("integration.py: sync requests.* calls forbidden — use httpx2.AsyncClient");
  }

  // --- 3. Timeout: owned by ast-grep/rules/integration/timeout-configured.yml ---
  // The regex here (`timeout\s*=|httpx2.Timeout`) was satisfied by
  // `except httpx2.TimeoutException` — an unrelated identifier. A pattern
  // matches the construction, so the claim is now structural.
  issues.push(
    ...runAstRules(join(projectRoot, ".omp", "ast-grep", "rules", "integration"), [integrationPath]),
  );

  // --- 4. Retry logic bounded by max_retries with exponential backoff ---
  if (!/max_retries/.test(integration)) {
    issues.push("integration.py: retry logic must be bounded by max_retries");
  }
  // Both halves of the formula are required: a base without a multiplier is
  // linear retry, a multiplier without the configured base ignores the
  // per-operation setting. The base is the operation's own `retry_base_ms`.
  if (!/retry_base_ms/.test(integration)) {
    issues.push("integration.py: backoff must start from the operation's retry_base_ms");
  }
  if (!/2\s*\*\*/.test(integration)) {
    issues.push("integration.py: backoff must be exponential (2 ** attempt)");
  }

  // --- 4b. Every retry is gated on operation.idempotent ---
  // Retrying a non-idempotent call repeats the side effect: a second charge, a
  // second order, a second message. The bound (max_retries) says how often, and
  // this says whether at all — so every backoff must sit under an idempotent
  // guard, not just somewhere in the same file.
  const lines = integration.split("\n");
  lines.forEach((line: string, index: number) => {
    if (!/await self\._backoff\(/.test(line)) return;
    const window = lines.slice(Math.max(0, index - 6), index).join("\n");
    if (!/self\.operation\.idempotent/.test(window)) {
      issues.push(
        `integration.py:${index + 1}: retry is not gated on operation.idempotent — ` +
          "retrying a non-idempotent call repeats the side effect",
      );
    }
  });

  // --- 5. Integration exceptions defined + handled ---
  if (!existsSync(exceptionsPath)) {
    // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
    issues.push("app/core/exceptions.py not found");
  } else {
    const exceptions = readFileSync(exceptionsPath, "utf-8");
    for (const name of ["IntegrationError", "IntegrationTimeoutError", "IntegrationRateLimitError"]) {
      if (!new RegExp(`class ${name}\\(`).test(exceptions)) {
        issues.push(`exceptions.py: ${name} class required`);
      }
    }
    if (!/IntegrationError/.test(exceptions) || !/@app\.exception_handler\(Integration/.test(exceptions)) {
      issues.push("exceptions.py: setup_exception_handler must register integration handlers");
    }
  }

  // --- 6. Shared HTTP client DI wiring ---
  if (!existsSync(depsPath)) {
    // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
    issues.push("app/dependencies/integrations.py not found — IntegrationHttpClientDep required");
  } else {
    const deps = readFileSync(depsPath, "utf-8");
    if (!/IntegrationHttpClientDep/.test(deps)) {
      issues.push("dependencies/integrations.py: IntegrationHttpClientDep Annotated alias required");
    }
    if (!/app\.state\.integration_http_client/.test(deps)) {
      issues.push("dependencies/integrations.py: must read app.state.integration_http_client");
    }
  }

  // --- 7. Shared client lifecycle in main.py lifespan ---
  if (!existsSync(mainPath)) {
    // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
    issues.push("app/main.py not found");
  } else {
    const main = readFileSync(mainPath, "utf-8");
    if (!/integration_http_client\s*=\s*httpx2\.AsyncClient/.test(main)) {
      issues.push("main.py: lifespan must create an integration_http_client AsyncClient");
    }
    // An unbounded pool turns one slow provider into every worker blocked on a
    // socket; the ceiling is what keeps a provider outage local to that provider.
    if (!/httpx2\.Limits\(/.test(main)) {
      issues.push(
        "main.py: the shared integration client needs httpx2.Limits(max_connections=...) — " +
          "an unbounded pool lets one slow provider consume every socket",
      );
    }
    if (!/await integration_http_client\.aclose\(\)/.test(main)) {
      issues.push("main.py: lifespan must close integration_http_client");
    }
  }

  issues.push(...checkTransportContainment());
  return issues;
}

/**
 * `httpx2` is confined to the sanctioned outbound path. Anywhere else it means a
 * second HTTP client with its own timeouts, retries, and error mapping — the
 * exact drift IntegrationClient exists to prevent.
 */
function checkTransportContainment(): string[] {
  const allowed = new Set([
    join("core", "integration.py"), // the client itself
    join("main.py"), // lifespan owns the shared client
    join("dependencies", "integrations.py"), // injects the shared client
  ]);
  // The service that passes the shared client through is one file or a folder
  // of them (`backend-model-files.md`) - listed from disk, so splitting the
  // service does not quietly turn its own transport use into a violation.
  for (const file of listDomainLayerFiles(join(appDir, "services"), "integration")) {
    allowed.add(join("services", file.slice(join(appDir, "services").length + 1)));
  }
  const issues: string[] = [];
  const walk = (dir: string, relative: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const relativePath = relative === "" ? entry.name : join(relative, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "__pycache__") continue;
        walk(join(dir, entry.name), relativePath);
        continue;
      }
      if (!entry.name.endsWith(".py") || allowed.has(relativePath)) continue;
      if (/\bhttpx2\b/.test(readFileSync(join(dir, entry.name), "utf-8"))) {
        issues.push(
          `app/${relativePath}: httpx2 is confined to core/integration.py and its wiring — ` +
            "call the service, never a second HTTP client",
        );
      }
    }
  };
  walk(appDir, "");
  return issues;
}

// Direct execution (make check-backend-integration): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-integration.ts")) {
  const issues = checkBackendIntegrationSync();
  console.log("==> check-backend-integration");
  if (issues.length === 0) {
    console.log("    PASS: external API integration standard valid");
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-integration");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
