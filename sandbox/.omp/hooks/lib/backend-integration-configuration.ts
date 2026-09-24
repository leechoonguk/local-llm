/**
 * Database-managed integration configuration checks
 * (.omp/rules/backend-integration-configuration.md).
 *
 * Validates the four-table standard end to end: the model tables and their
 * constraints, the schema classes and their order, repository eager-loading,
 * service validation, the router surface, secret containment, the seed
 * migrations, and the external API contract tests.
 *
 * Migration and seeded-operation discovery is delegated to
 * backend-migration-policy.ts — this module never hardcodes a revision list.
 */
// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readFileSync, readdirSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";
import {
  listIntegrationMigrationFiles,
  listIntegrationOperationCodes,
  listMisnamedSeedFiles,
  listUnknownSeedColumns,
  listWireNamedCallerKeys,
} from "./backend-migration-policy.ts";
import { listDomainLayerFiles, readLayerSource } from "./backend-domain-structure.ts";

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app"))
  ? cwd
  : join(cwd, "..");
const backendRoot = join(projectRoot, "backend");

/**
 * This hook is the `integration` domain's dedicated contract checker, so it
 * names its own domain - the one case the domain-literal gate allows, read
 * from this file's name rather than from a list (`omp-hooks.md`).
 */
const DOMAIN = "integration";

/**
 * Where a schema class sits in the request's life: the base and the create
 * pair, the read response, the update pair, then the execute pair. Derived
 * from the suffix, so a new table's classes rank themselves.
 *
 * `null` means "not one of the standard shapes" - ordering says nothing about
 * it, so it is skipped rather than treated as rank zero.
 */
function schemaClassRank(name: string): number | null {
  if (/Base$/.test(name) || /Create(Request|Internal)$/.test(name)) return 0;
  if (/ReadResponse$/.test(name)) return 1;
  if (/Update(Request|Internal)$/.test(name)) return 2;
  if (/Execute(Request|Response)$/.test(name)) return 3;
  return null;
}

/**
 * The classes this domain's schema layer must expose, wherever in the folder
 * they live. This is the contract itself (`backend-integration-configuration.md`),
 * not an exemption list - which is why it is spelled out here, in the domain's
 * own checker, and why ordering is derived rather than listed.
 */
const REQUIRED_SCHEMA_CLASSES = [
  "IntegrationBase",
  "IntegrationCreateRequest",
  "IntegrationCreateInternal",
  "IntegrationReadResponse",
  "IntegrationUpdateRequest",
  "IntegrationUpdateInternal",
  "IntegrationSecretCreateRequest",
  "IntegrationSecretUpdateRequest",
  "IntegrationSecretReadResponse",
  "IntegrationFieldCreateRequest",
  "IntegrationFieldReadResponse",
  "IntegrationOperationCreateRequest",
  "IntegrationOperationReadResponse",
  "IntegrationExecuteRequest",
  "IntegrationExecuteResponse",
];

/**
 * A seeded operation states its window width.
 *
 * `integration_operation.page_size` carries a `server_default`, so a seed that
 * does not name it is silently 100. Measured: eleven 식품안전나라
 * operations were seeded that way when the width moved from the job to the
 * operation, and the jobs that had walked those feeds in 1,000-row pages went on
 * walking them in 100-row ones - the barcode feed took 2,462 windows and 7.5
 * hours against 247 windows, per-window latency climbing 1.1 s → 12 s with the
 * offset, and ten times the calls spent fifteen refusals and locked all three
 * keys for an hour. The width a portal answers is a measurement; a default is
 * not one.
 */
const WINDOW_RULE_FROM_REVISION = 269;

function checkSeededOperationsStateTheirWindow(): string[] {
  const issues: string[] = [];
  const versionsDir = join(backendRoot, "alembic", "versions");
  if (!existsSync(versionsDir)) return issues;
  for (const filename of readdirSync(versionsDir)) {
    if (!filename.endsWith(".py") || !filename.includes("_integration_operation")) continue;
    if (!filename.includes("_seed_") && !filename.includes("_replace_")) continue;
    const content = readFileSync(join(versionsDir, filename), "utf-8");
    // Applied history is history: revision 269 corrected the eleven 식품안전나라
    // operations that had drifted onto the default, and editing the seeds that
    // wrote them would rewrite migrations every environment has already run.
    // The rule binds every revision written after that correction.
    const number = Number(/^(\d+)_/.exec(filename)?.[1] ?? 0);
    if (number <= WINDOW_RULE_FROM_REVISION) continue;
    if (!/bulk_insert|\.insert\(/.test(content)) continue;
    if (/"page_size"|page_size=/.test(content)) continue;
    issues.push(
      `alembic/versions/${filename}: seeds an integration operation without a page_size - ` +
        "the column's server_default is 100, so a walk that used to read 1,000 rows a window " +
        "silently reads ten times as many windows (measured on the barcode feed: " +
        "ten times the windows, hours instead of minutes)",
    );
  }
  return issues;
}


export function checkIntegrationConfiguration(): string[] {
  const issues: string[] = [...checkSeededOperationsStateTheirWindow()];
  // Every layer of this domain is several files, so each side of the contract
  // is read as the whole layer, not one path. `listDomainLayerFiles` and
  // `readLayerSource` answer that for a flat `<domain>_*.py` split and for the
  // `<domain>/` folder alike (`backend-model-files.md`), so this hook does not
  // carry a second opinion about where a domain's files live - it carried one
  // before, and the folder move turned three of these checks into no-ops that
  // still reported success.
  const appDir = join(backendRoot, "app");
  const modelFiles = listDomainLayerFiles(join(appDir, "models"), DOMAIN);
  const repositoryFiles = listDomainLayerFiles(join(appDir, "repositories"), DOMAIN);
  const schemaSource = readLayerSource(join(appDir, "schemas"), DOMAIN);
  const serviceSourceText = readLayerSource(join(appDir, "services"), DOMAIN);
  const routerPath = join(appDir, "routers", `${DOMAIN}.py`);
  const clientPath = join(appDir, "core", `${DOMAIN}.py`);
  const settingsPath = join(appDir, "core", "settings.py");
  const integrationTestPath = join(backendRoot, "tests", "core", `test_${DOMAIN}.py`);
  const externalApiTestPath = join(
    backendRoot,
    "tests",
    "core",
    `test_${DOMAIN}_external_api.py`,
  );
  const requiredPaths = [
    [routerPath, `app/routers/${DOMAIN}.py`],
    [clientPath, `app/core/${DOMAIN}.py`],
    [integrationTestPath, `tests/core/test_${DOMAIN}.py`],
    [externalApiTestPath, `tests/core/test_${DOMAIN}_external_api.py`],
  ] as const;
  if (modelFiles.length === 0) {
    issues.push(`app/models/${DOMAIN}/<table>.py is required - one file per table`);
  }
  if (repositoryFiles.length === 0) {
    issues.push(`app/repositories/${DOMAIN}/<table>.py is required - one file per table`);
  }
  if (schemaSource === null) {
    issues.push(`app/schemas/${DOMAIN}/*.py is required`);
  }
  if (serviceSourceText === null) {
    issues.push(`app/services/${DOMAIN}.py is required`);
  }
  for (const [path, label] of requiredPaths) {
    if (!existsSync(path)) issues.push(`${label} is required`);
  }
  if (issues.length > 0 || schemaSource === null || serviceSourceText === null) return issues;

  const model = modelFiles.map((file: string) => readFileSync(file, "utf-8")).join("\n");
  for (const table of [
    "integration_provider",
    "integration_secret",
    "integration_operation",
    "integration_field",
  ]) {
    if (!model.includes(`__tablename__ = \"${table}\"`)) {
      issues.push(`models/integration_*.py: ${table} table is required`);
    }
  }
  if (/config_revision/.test(model)) {
    issues.push(
      "models/integration_*.py: config_revision is outside the live-configuration standard",
    );
  }
  // A secret is a named row owned by the provider, resolved through a field FK.
  // Storing the value on the field row loses it whenever fields are replaced.
  if (!/class IntegrationSecret\b/.test(model) || !/secret_id/.test(model)) {
    issues.push(
      "models/integration_*.py: named secrets require IntegrationSecret plus a field secret_id FK",
    );
  }
  if (/\b(secret_ref|secret_value|literal_value|default_value|source_key)\b/.test(model)) {
    issues.push(
      "models/integration_*.py: sparse value columns are replaced by value + secret_id",
    );
  }
  if (!/response_root/.test(model)) {
    issues.push(
      "models/integration_*.py: response_root defines the response contract — absent maps a " +
        "record, present maps every element of the page it names",
    );
  }
  if (/response_mode/.test(model)) {
    issues.push(
      "models/integration_*.py: response_mode is removed — mapping is the only response " +
        "contract, so a mode column carries one legal value",
    );
  }
  if (/response_schema/.test(model)) {
    issues.push(
      "models/integration_*.py: response_schema duplicated the response field rows — removed",
    );
  }

  const schema = schemaSource;
  // Read models expose a secret by name only; the value never leaves the database.
  if (
    !/class IntegrationSecretReadResponse\b/.test(schema) ||
    /class IntegrationSecretReadResponse[\s\S]*?\n\n/.exec(schema)?.[0].includes("value: str")
  ) {
    issues.push(
      "schemas/integration.py: IntegrationSecretReadResponse must omit the secret value",
    );
  }
  // Schema naming: every HTTP-facing class carries a Request/Response suffix
  // (backend-domain.md). Suffix-free classes are limited to Base and Internal.
  const schemaClasses = [
    ...schema.matchAll(/^class\s+(\w+)/gm),
  ].map((m) => m[1]);
  for (const cls of schemaClasses) {
    if (
      !cls.endsWith("Request") &&
      !cls.endsWith("Response") &&
      !cls.endsWith("Base") &&
      !cls.endsWith("Internal")
    ) {
      issues.push(
        `schemas/integration.py: class ${cls} must carry a Request or Response suffix ` +
          "(only Base/Internal classes are suffix-free)",
      );
    }
  }
  // Class ordering: create-side, then read-side, then update-side, then the
  // execute pair - the order a reader follows a request through.
  //
  // The rank comes from the class suffix, not from a list of the thirteen
  // classes that happened to exist. That list also encoded a single-file
  // reading order, so splitting the layer into `schemas/integration/*.py` made
  // it fail on a grouping that is strictly better: each file now holds one
  // table's request and response next to each other. Ordering is a per-file
  // property, so it is now checked per file.
  for (const file of listDomainLayerFiles(join(appDir, "schemas"), DOMAIN)) {
    const source = readFileSync(file, "utf-8");
    const label = `schemas/${DOMAIN}/${file.split("/").pop()}`;
    let lastRank = -1;
    let lastClass = "";
    for (const match of source.matchAll(/^class (\w+)\b/gm)) {
      const cls = match[1];
      const rank = schemaClassRank(cls);
      if (rank === null) continue;
      if (rank < lastRank) {
        issues.push(
          `${label}: class ${cls} is out of order - create-side, then read-side, ` +
            `then update-side, then the execute pair (it follows ${lastClass})`,
        );
      }
      lastRank = Math.max(lastRank, rank);
      lastClass = cls;
    }
  }
  for (const cls of REQUIRED_SCHEMA_CLASSES) {
    if (!schemaClasses.includes(cls)) {
      issues.push(`schemas/${DOMAIN}/*.py: required class ${cls} is missing`);
    }
  }
  if (schemaClasses.indexOf("to_read") !== -1) {
    issues.push(`schemas/${DOMAIN}/provider.py: to_read is a function, not a class`);
  }
  // Every Read class exposes the optimistic-lock revision its caller holds.
  for (const readClass of [
    "IntegrationSecretReadResponse",
    "IntegrationFieldReadResponse",
    "IntegrationOperationReadResponse",
    "IntegrationReadResponse",
  ]) {
    const body = new RegExp(`class ${readClass}\\(\\w+\\):\\n((?:[ \\t].*\\n|\\n)*)`).exec(schema);
    if (body !== null && !/^\s+version:\s*int/m.test(body[1])) {
      issues.push(`schemas/integration.py: ${readClass} must expose version: int`);
    }
  }

  const repository = repositoryFiles.map((file: string) => readFileSync(file, "utf-8")).join("\n");
  if (
    !/async def get_operation\(/.test(repository) ||
    !/selectinload\(IntegrationOperation/.test(repository)
  ) {
    issues.push(
      "repositories/integration_operation.py: operation resolution must eager-load " +
        "configuration children",
    );
  }

  const service = serviceSourceText;
  if (!/Draft202012Validator\.check_schema/.test(service)) {
    issues.push(
      "services/integration.py: JSON Schema 2020-12 configuration validation is required",
    );
  }
  if (
    !/"SECRET"/.test(service) ||
    !/FORBIDDEN_REQUEST_HEADERS/.test(service)
  ) {
    issues.push(
      "services/integration.py: request source and transport header validation is required",
    );
  }
  if (/SECRET_REF/.test(service)) {
    issues.push(
      "services/integration.py: SECRET_REF was replaced by a named SECRET reference",
    );
  }

  const router = readFileSync(routerPath, "utf-8");
  // The router injects this domain's service DI. Which aliases exist depends on
  // how the service layer is split, so the check is "a service alias for this
  // domain", not one alias name that a split renames out of existence.
  const injectsDomainService = new RegExp(
    `Integration\\w*ServiceDep\\b`,
  ).test(router);
  if (!new RegExp(`prefix="/${DOMAIN}"`).test(router) || !injectsDomainService) {
    issues.push(
      `routers/${DOMAIN}.py: authenticated integration configuration CRUD is required`,
    );
  }

  const client = readFileSync(clientPath, "utf-8");
  if (
    !/async def from_database\(/.test(client) ||
    !/async def execute\(/.test(client)
  ) {
    issues.push(
      "core/integration.py: database resolution and execute() are required",
    );
  }
  if (
    !/IntegrationExecutionResult/.test(client) ||
    !/Draft202012Validator/.test(client)
  ) {
    issues.push(
      "core/integration.py: canonical execution result and schema validation are required",
    );
  }
  if (/async def request\(/.test(client) || /response_model=/.test(client)) {
    issues.push(
      "core/integration.py: legacy raw request or response-model API is forbidden",
    );
  }

  if (!existsSync(settingsPath) || /integration_secrets/.test(readFileSync(settingsPath, "utf-8"))) {
    issues.push(
      "core/settings.py: integration_secrets env mapping is forbidden — secrets live in integration_secret",
    );
  }
  // The client reads the secret through the field's FK, so a rotated secret takes
  // effect without touching any field row.
  if (!/field\.secret\b/.test(client) || !/secret\.value/.test(client)) {
    issues.push(
      "core/integration.py: SECRET values must resolve through the field's integration_secret FK",
    );
  }
  if (/response_schema|operation\.(request_fields|response_fields|response_headers)/.test(client)) {
    issues.push(
      "core/integration.py: the three child collections were unified into operation.fields",
    );
  }
  if (!/response_root/.test(client)) {
    issues.push(
      "core/integration.py: response_root decides what the RESPONSE rows are resolved against",
    );
  }
  if (/response_mode/.test(client)) {
    issues.push(
      "core/integration.py: response_mode is removed — the rows always build the payload",
    );
  }
  if (!/for record in page/.test(client)) {
    issues.push(
      "core/integration.py: a page root must map every element — pinning one record made " +
        "the caller's page size unobservable (measured)",
    );
  }
  issues.push(...checkFileOperations(backendRoot, client));

  const externalApiTest = readFileSync(externalApiTestPath, "utf-8");
  for (const [needle, label] of [
    [
      "test_execute_renders_the_seeded_contract",
      "fixture-driven contract test",
    ],
    [
      "test_mfds_seed_migration_persists_executable_configuration",
      "MFDS seed migration test",
    ],
    ["MigrationContext.configure", "isolated migration execution"],
    ["description", "request/response field description seed assertion"],
  ]) {
    if (!externalApiTest.includes(needle)) {
      issues.push(`tests/core/test_integration_external_api.py: ${label} is required`);
    }
  }

  const integrationMigrations = listIntegrationMigrationFiles();
  if (integrationMigrations.length === 0) {
    issues.push("alembic/versions: integration migrations are required");
  }
  for (const table of [
    "integration_provider",
    "integration_secret",
    "integration_operation",
    "integration_field",
  ]) {
    if (!integrationMigrations.some((filename) => filename.includes(table))) {
      issues.push(`alembic/versions: ${table} migration is required`);
    }
  }
  if (
    !externalApiTest.includes('glob("*_seed_*_integration_*.py")') &&
    !externalApiTest.includes('"*_seed_*_integration_*.py"')
  ) {
    issues.push(
      "tests/core/test_integration_external_api.py: integration seed migration discovery is required",
    );
  }
  // The requirement is one recorded exchange per operation, not a hand-written
  // test: the field list already exists in the seed, and restating it cost 191
  // lines per operation - the step a small model never reached in a measured run.
  // So the message names the file to create and a sibling to copy.
  const fixtureDir = join(backendRoot, "tests", "core", "fixtures", "integration");
  const fixtures = existsSync(fixtureDir) ? readdirSync(fixtureDir) : [];
  for (const operationCode of listIntegrationOperationCodes()) {
    if (fixtures.includes(`${operationCode}.json`)) continue;
    const sibling = fixtures.find((name: string) => name.endsWith(".json"));
    issues.push(
      `tests/core/fixtures/integration/${operationCode}.json is missing — record one measured ` +
        `exchange for '${operationCode}' (inputs, response, expect.path/query/canonical_payload)` +
        (sibling === undefined ? "" : `, copying the shape of ${sibling}`),
    );
  }

  // A seed that binds a column the model does not declare fails at runtime, deep
  // inside a test. The model file is the schema; the binding must copy it.
  issues.push(...listUnknownSeedColumns());

  // The filename is the only identity a reader sees before opening the file, and
  // a superseding revision is only unambiguous when the two files share a name.
  issues.push(...listMisnamedSeedFiles());

  // The caller-facing key is the contract; the wire name is the provider's. A run
  // that seeds `chng_dt` for `CHNG_DT` passed every other hook and all 150 tests.
  issues.push(...listWireNamedCallerKeys());

  // A fixture is only worth having if it carries the measured halves. `path` is
  // singled out because a placeholder there passes every other check while
  // proving nothing: the rendered path is what the provider judges.
  for (const name of fixtures.filter((file: string) => file.endsWith(".json"))) {
    const label = `tests/core/fixtures/integration/${name}`;
    let fixture: Record<string, unknown>;
    try {
      fixture = JSON.parse(readFileSync(join(fixtureDir, name), "utf-8")) as Record<string, unknown>;
    } catch (error: unknown) {
      issues.push(`${label}: not readable as JSON - ${String(error)}`);
      continue;
    }
    for (const key of ["why", "inputs", "response", "expect"]) {
      if (!(key in fixture)) issues.push(`${label}: '${key}' is required`);
    }
    const expect = (fixture.expect ?? {}) as Record<string, unknown>;
    const path = typeof expect.path === "string" ? expect.path : "";
    if (path === "" || path === "TBD" || !path.startsWith("/")) {
      issues.push(`${label}: expect.path must be the measured request path, not '${path}'`);
    }
    const refuses = typeof expect.raises === "string";
    if (!refuses && !("canonical_payload" in expect)) {
      issues.push(
        `${label}: a success fixture states expect.canonical_payload, and a refusal states expect.raises`,
      );
    }
    // The whole point of reading the seeds is that the rows are not restated.
    if (/"(value_source|wire_path|direction)"\s*:/.test(readFileSync(join(fixtureDir, name), "utf-8"))) {
      issues.push(
        `${label}: restates seeded field rows - a fixture records one exchange, and the field list ` +
          "belongs to the seed migration",
      );
    }
  }

  // The pattern must not come back one operation at a time.
  for (const match of externalApiTest.matchAll(/def (test_execute_renders_[a-z0-9_]+_contract)\b/g)) {
    if (match[1] === "test_execute_renders_the_seeded_contract") continue;
    issues.push(
      `tests/core/test_integration_external_api.py: ${match[1]} is a hand-written per-operation ` +
        "contract test - record a fixture in tests/core/fixtures/integration/ instead; the seeds " +
        "already carry the field list",
    );
  }

  // External API spec fidelity: the newest request/response field seed must
  // carry `description` for every row, and the response_schema must use
  // nullable types — public APIs return null for unpopulated fields, and a
  // non-nullable type turns a normal sparse response into a 502.
  const fieldSeeds = integrationMigrations.filter(
    (filename) =>
      (filename.includes("_seed_") || filename.includes("_replace_")) &&
      (filename.includes("integration_request_field") ||
        filename.includes("integration_response_field")),
  );
  const newestFieldSeed = fieldSeeds[fieldSeeds.length - 1];
  if (newestFieldSeed !== undefined) {
    const seed = readFileSync(
      join(backendRoot, "alembic", "versions", newestFieldSeed),
      "utf-8",
    );
    if (!/column\("description"/.test(seed)) {
      issues.push(
        `alembic/versions/${newestFieldSeed}: every seeded field needs a description column (provider spec text)`,
      );
    }
  }
  const operationSeeds = integrationMigrations.filter(
    (filename) =>
      (filename.includes("_seed_") || filename.includes("_replace_")) &&
      filename.includes("integration_operation"),
  );
  const newestOperationSeed = operationSeeds[operationSeeds.length - 1];
  if (newestOperationSeed !== undefined) {
    const seed = readFileSync(
      join(backendRoot, "alembic", "versions", newestOperationSeed),
      "utf-8",
    );
    if (/RESPONSE_SCHEMA/.test(seed) && !/"null"/.test(seed)) {
      issues.push(
        `alembic/versions/${newestOperationSeed}: response_schema property types must be nullable (["string", "null"]) — public APIs return null for unpopulated fields`,
      );
    }
  }

  // Response format support: both JSON and XML decode through the same pointer
  // mapping, so the model must carry response_format and the client must branch
  // on it. A JSON-only client silently 502s every XML provider.
  if (!/response_format/.test(model)) {
    issues.push(
      "models/integration_*.py: integration_operation.response_format (JSON|XML) is required",
    );
  }
  if (!/response_format/.test(schema)) {
    issues.push(
      "schemas/integration.py: response_format must be configurable on operations",
    );
  }
  if (!/ElementTree/.test(client) || !/response_format == "XML"/.test(client)) {
    issues.push(
      "core/integration.py: XML response decoding (ElementTree + response_format branch) is required",
    );
  }
  if (!/not valid XML/.test(client)) {
    issues.push(
      "core/integration.py: malformed XML must map to IntegrationError, not a parser traceback",
    );
  }

  // The key pool is a property of the secret and a decision of the operation
  // service: a provider's grouped secrets answer as one credential, and the
  // service turns the pool on a quota code. Nothing above the service may know
  // the pool exists - a batch job or a router that reads `exhausted_until` or
  // picks a member has re-implemented the rotation once, and the copy that
  // forgets to mark the spent key sends it again every window.
  const poolWords = /\b(rotation_group|exhausted_until|list_pool|mark_exhausted)\b/;
  for (const layer of ["batch", "routers", "dependencies"]) {
    const layerDir = join(appDir, layer);
    if (!existsSync(layerDir)) continue;
    for (const file of readdirSync(layerDir).filter((name: string) => name.endsWith(".py"))) {
      if (poolWords.test(readFileSync(join(layerDir, file), "utf-8"))) {
        issues.push(
          `${layer}/${file}: reads the secret pool - the rotation is the operation service's; ` +
            "a caller sees one credential and the provider's refusal only when every key is spent",
        );
      }
    }
  }
  if (!/quota_codes/.test(serviceSourceText) || !/mark_exhausted/.test(serviceSourceText)) {
    issues.push(
      "services/integration: the operation service must turn the pool on a quota code and mark the spent member",
    );
  }

  // A screen is a transport, not a second stack (rule: "A Screen Is a Transport").
  // Every trap below was measured on the first one (impfood).
  issues.push(...listScreenDefects(fixtureDir));

  return issues;
}

/**
 * The seeded operations whose `response_format` is HTML, each with the facts the
 * screen checks read: the provider seed's transport, the form media type, the
 * request schema, the row selector.
 */
function listScreenOperations(): Array<{
  code: string;
  file: string;
  provider: string;
  transportSeeded: boolean;
  formMedia: boolean;
  exactForm: boolean;
  root: string | null;
}> {
  const versionsDir = join(backendRoot, "alembic", "versions");
  if (!existsSync(versionsDir)) return [];
  const files = readdirSync(versionsDir).filter((f: string) => f.endsWith(".py")).sort();
  const contents = new Map<string, string>();
  for (const f of files) contents.set(f, readFileSync(join(versionsDir, f), "utf-8") as string);
  const newest = new Map<string, { file: string; content: string }>();
  for (const [file, content] of contents) {
    if (!/"response_format":\s*"HTML"/.test(content)) continue;
    const code = /"code":\s*"([a-z0-9-]+)"/.exec(content)?.[1];
    if (code === undefined) continue;
    newest.set(code, { file, content });
  }
  const screens: ReturnType<typeof listScreenOperations> = [];
  for (const [code, { file, content }] of newest) {
    const providerId = /PROVIDER_ID\s*=\s*uuid5\([^,]+,\s*"([^"]+)"\)/.exec(content)?.[1] ?? "";
    let provider = "";
    let transportSeeded = false;
    for (const [, other] of contents) {
      if (!other.includes(`"${providerId}"`) || !/"integration_provider"/.test(other)) continue;
      provider = /"code":\s*"([a-z0-9-]+)"/.exec(other)?.[1] ?? provider;
      transportSeeded = /"transport":\s*"HTML_FORM"/.test(other) || transportSeeded;
    }
    const formMedia = /"request_media_type":\s*"(multipart\/form-data|application\/x-www-form-urlencoded)"/.test(content);
    const exactForm =
      /"additionalProperties":\s*False/.test(content) && /"required":\s*FORM_FIELDS/.test(content);
    const rootMatch = /"response_root":\s*(?:"([^"]*)"|([A-Z_][A-Z0-9_]*))/.exec(content);
    const root =
      rootMatch === null
        ? null
        : (rootMatch[1] ?? new RegExp(`^${rootMatch[2]}\\s*=\\s*"([^"]*)"`, "m").exec(content)?.[1] ?? null);
    screens.push({ code, file, provider, transportSeeded, formMedia, exactForm, root });
  }
  return screens;
}

/**
 * What a screen feed has to have recorded, because each was a live defect:
 *
 * - the provider is seeded `HTML_FORM` - without the session bootstrap the list
 *   POST answers `302 -> /error/error`;
 * - a form operation's request schema closes the field set
 *   (`additionalProperties: False`, `required: FORM_FIELDS`) - the screen refused
 *   the request when three inputs its own JS never posts were added;
 * - the row selector is not a pointer;
 * - the fixture carries `expect.form` (the measured parts) and
 *   `expect.bootstrap_path`, and a second fixture `<code>.empty.json` records the
 *   empty state - a placeholder row the selector must exclude, or the walk
 *   would stage 조회 결과가 없습니다 as a record and never see the end.
 */
function listScreenDefects(fixtureDir: string): string[] {
  const issues: string[] = [];
  for (const screen of listScreenOperations()) {
    const label = `alembic/versions/${screen.file}`;
    if (!screen.transportSeeded) {
      issues.push(
        `${label}: ${screen.code} answers HTML but its provider ${screen.provider || "(unresolved)"} ` +
          "is not seeded transport HTML_FORM - the list POST answers the error page without the session",
      );
    }
    if (screen.formMedia && !screen.exactForm) {
      issues.push(
        `${label}: ${screen.code} posts a form, so its request_schema must close the field set - ` +
          '"required": FORM_FIELDS and "additionalProperties": False (one extra part is a refusal)',
      );
    }
    if (screen.root !== null && screen.root.startsWith("/")) {
      issues.push(`${label}: ${screen.code} is HTML, so response_root is a row selector, not a pointer`);
    }
    const fixturePath = join(fixtureDir, `${screen.code}.json`);
    if (existsSync(fixturePath)) {
      const expect = (JSON.parse(readFileSync(fixturePath, "utf-8")).expect ?? {}) as Record<string, unknown>;
      if (screen.formMedia && typeof expect.form !== "object") {
        issues.push(
          `tests/core/fixtures/integration/${screen.code}.json: a form screen's fixture records the parts ` +
            "the browser posts in expect.form - the field set is the contract",
        );
      }
      if (screen.transportSeeded && typeof expect.bootstrap_path !== "string") {
        issues.push(
          `tests/core/fixtures/integration/${screen.code}.json: expect.bootstrap_path names the screen ` +
            "whose GET mints the session, so the fixture proves the cookie is fetched first",
        );
      }
    }
    const emptyPath = join(fixtureDir, `${screen.code}.empty.json`);
    if (!existsSync(emptyPath)) {
      issues.push(
        `tests/core/fixtures/integration/${screen.code}.empty.json is missing - record the screen's empty ` +
          "state (the page past the last one) and expect canonical_payload [], because a screen draws " +
          "'no rows' as a row and the walk ends only when the selector excludes it",
      );
      continue;
    }
    const empty = JSON.parse(readFileSync(emptyPath, "utf-8")) as Record<string, unknown>;
    const expect = (empty.expect ?? {}) as Record<string, unknown>;
    const payload = expect.canonical_payload;
    // A screen that pages is empty as an empty page; a screen that answers one
    // record is empty as a refusal, because its envelope row is what tells "no
    // such key" from a record of blanks (measured: an unknown 접수번호 answers
    // 200 with the same table drawn and every cell empty).
    const emptyPage = Array.isArray(payload) && payload.length === 0;
    const refusal = typeof expect.raises === "string";
    if (!emptyPage && !refusal) {
      issues.push(
        `tests/core/fixtures/integration/${screen.code}.empty.json: the empty state is either an ` +
          "empty page (expect.canonical_payload []) or a refusal (expect.raises), never a record of blanks",
      );
    }
  }
  return issues;
}


/**
 * A file operation (`response_format` CSV) is one request answering the whole
 * feed, read in chunks. Three shapes cannot apply to it and one must:
 *
 * - no ENVELOPE row — a file's success has no wrapper and its refusal is an
 *   HTTP 429 (measured on 식품안전나라 I0460: `INFO-500` and `INFO-330` both
 *   arrive as 429 with an XML body; decks/ledger-measurements §14);
 * - no paging input — a chunk of `page_size` rows is the walk's page, and a
 *   window sent to the file door is ignored;
 * - no `response_root` — the file is the page;
 * - a fixture recording the gzip bytes (`response.gzip_base64`) and the rows
 *   the reader produced from them (`expect.rows`), because the reader is what
 *   a file operation adds and a JSON fixture proves none of it.
 *
 * And the client must be able to read one: `stream` and the record cutter
 * exist, or the seed names a format nothing can walk.
 */
function checkFileOperations(backendRoot: string, client: string): string[] {
  const issues: string[] = [];
  const versions = join(backendRoot, "alembic", "versions");
  const files = existsSync(versions) ? readdirSync(versions).filter((f: string) => f.endsWith(".py")) : [];
  const byRevision = (a: string, b: string) => Number.parseInt(a, 10) - Number.parseInt(b, 10);
  const operationSeeds = files.filter((f: string) => f.includes("integration_operation")).sort(byRevision);
  const fieldSeeds = files.filter((f: string) => f.includes("integration_field")).sort(byRevision);
  const newestFormat = new Map<string, { file: string; csv: boolean; root: boolean }>();
  for (const file of operationSeeds) {
    const content = readFileSync(join(versions, file), "utf-8");
    const code = /"code":\s*"([^"]+)"/.exec(content)?.[1];
    if (code === undefined) continue;
    newestFormat.set(code, {
      file,
      csv: /"response_format":\s*"CSV"/.test(content),
      root: /"response_root":\s*(?:"|[A-Z_]+,)/.test(content),
    });
  }
  const fileOperations = [...newestFormat].filter(([, seed]) => seed.csv);
  if (fileOperations.length === 0) return issues;
  if (!/async def stream\(/.test(client) || !/class _RecordCutter/.test(client)) {
    issues.push(
      "core/integration.py: a CSV operation is seeded, so the client must read a file - " +
        "`stream` in chunks of page_size, with the RFC 4180 record cutter",
    );
  }
  for (const [code, seed] of fileOperations) {
    const label = `alembic/versions/${seed.file}`;
    if (seed.root) {
      issues.push(`${label}: a CSV operation has no response_root - the file is the page`);
    }
    const fields = fieldSeeds
      .filter((f: string) => readFileSync(join(versions, f), "utf-8").includes(`/${code}"`))
      .at(-1);
    if (fields !== undefined) {
      const content = readFileSync(join(versions, fields), "utf-8");
      if (/ENVELOPE_ROWS\s*=\s*\[\s*\(/.test(content)) {
        issues.push(`alembic/versions/${fields}: a CSV operation reads no envelope - a file's refusal is its status`);
      }
      if (/'(range_start|range_end|page_no|num_of_rows)'/.test(content)) {
        issues.push(`alembic/versions/${fields}: a CSV operation is read in chunks of page_size, not windowed`);
      }
    }
    const fixture = join(backendRoot, "tests", "core", "fixtures", "integration", `${code}.json`);
    const recorded = existsSync(fixture) ? readFileSync(fixture, "utf-8") : "";
    if (!/"gzip_base64"/.test(recorded) || !/"rows"/.test(recorded)) {
      issues.push(
        `tests/core/fixtures/integration/${code}.json: a file operation's fixture records the gzip ` +
          "bytes (response.gzip_base64) and the rows the reader produced (expect.rows)",
      );
    }
  }
  return issues;
}
