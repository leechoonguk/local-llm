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

export function checkIntegrationConfiguration(): string[] {
  const issues: string[] = [];
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

  return issues;
}
