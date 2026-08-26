/**
 * Check-Backend-FileUpload Post Hook
 *
 * Validates backend-file-upload.md: UploadFile with size limit and content-type allowlist
 * Optional feature — checked only when present; absence is not a violation.
 *
 * This is a read-only check — it does NOT block tool calls.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import { buildSafeWarning, wrapWarning, resetSuppression } from "../lib/hook-safety-guard.ts";
import { dormant, passLine } from "../lib/hook-dormancy.ts";
import { runAstRules } from "../lib/ast-rules.ts";
import { guarded } from "../lib/hook-visibility.ts";
import { printRuleHint } from "../lib/hook-rule-hint.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");
const appDir = join(projectRoot, "backend", "app");

const MUTATING_TOOLS = new Set([
  "write", "edit", "bash", "eval", "ast_edit", "lsp", "browser", "hub", "task",
]);


export default function checkBackendFileUpload(pi: ExtensionAPI): void {
  pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) => guarded("check-backend-file-upload", event, () => {
    if (event.toolName && !MUTATING_TOOLS.has(event.toolName)) return;

    const issues = checkBackendFileUploadSync();
    if (issues.length === 0) {
      resetSuppression("check-backend-file-upload");
      return;
    }
    const warning = buildSafeWarning(
      event.toolName,
      "check-backend-file-upload",
      issues,
      "run make check-backend-file-upload for details",
    );
    if (warning === null) return;
    console.error(warning);
    return { content: wrapWarning(warning, event.content, "check-backend-file-upload") };
  }));
}

function checkBackendFileUploadSync(): string[] {
  const issues: string[] = [];

  // `ast-grep/rules/upload/no-size-guard.yml` is the sole owner: it matches the
  // handler that takes an UploadFile and searches its body for the size and
  // content-type guards, per function rather than per file.
  const uploadRules = join(projectRoot, ".omp", "ast-grep", "rules", "upload");
  if (existsSync(uploadRules)) {
    issues.push(...runAstRules(uploadRules, [join(appDir, "routers")]));
  }
  if (!routersMention("UploadFile")) {
    return dormant("check-backend-file-upload", "no UploadFile parameter in app/routers");
  }
  return issues;
}

/** Whether any router mentions the marker — the feature's presence in this app. */
function routersMention(marker: string): boolean {
  const routersDir = join(appDir, "routers");
  if (!existsSync(routersDir)) return false;
  return readdirSync(routersDir)
    .filter((file: string) => file.endsWith(".py"))
    .some((file: string) => readFileSync(join(routersDir, file), "utf-8").includes(marker));
}

// Direct execution (make check-backend-file-upload): run the check and print results.
if (typeof process !== "undefined" && process.argv[1]?.endsWith("check-backend-file-upload.ts")) {
  const issues = checkBackendFileUploadSync();
  console.log("==> check-backend-file-upload");
  if (issues.length === 0) {
    console.log(passLine("check-backend-file-upload", "backend file-upload standard valid"));
    process.exit(0);
  }
  for (const issue of issues) {
    console.log(`    FAIL: ${issue}`);
  }
  printRuleHint("check-backend-file-upload");
  console.log(`    ${issues.length} issue(s) found`);
  process.exit(1);
}
