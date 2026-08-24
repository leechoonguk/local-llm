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

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app"))
  ? cwd
  : join(cwd, "..");
const backendRoot = join(projectRoot, "backend");

export function checkIntegrationConfiguration(): string[] {
  const issues: string[] = [];
  const modelPath = join(backendRoot, "app", "models", "integration.py");
  const schemaPath = join(backendRoot, "app", "schemas", "integration.py");
  const repositoryPath = join(
    backendRoot,
    "app",
    "repositories",
    "integration.py",
  );
  const servicePath = join(backendRoot, "app", "services", "integration.py");
  const routerPath = join(backendRoot, "app", "routers", "integration.py");
  const clientPath = join(backendRoot, "app", "core", "integration.py");
  const settingsPath = join(backendRoot, "app", "core", "settings.py");
  const integrationTestPath = join(
    backendRoot,
    "tests",
    "core",
    "test_integration.py",
  );
  const externalApiTestPath = join(
    backendRoot,
    "tests",
    "core",
    "test_integration_external_api.py",
  );
  const requiredPaths = [
    [modelPath, "app/models/integration.py"],
    [schemaPath, "app/schemas/integration.py"],
    [repositoryPath, "app/repositories/integration.py"],
    [servicePath, "app/services/integration.py"],
    [routerPath, "app/routers/integration.py"],
    [clientPath, "app/core/integration.py"],
    [integrationTestPath, "tests/core/test_integration.py"],
    [externalApiTestPath, "tests/core/test_integration_external_api.py"],
  ] as const;
  for (const [path, label] of requiredPaths) {
    if (!existsSync(path)) issues.push(`${label} is required`);
  }
  if (issues.length > 0) return issues;

  const model = readFileSync(modelPath, "utf-8");
  for (const table of [
    "integration_provider",
    "integration_secret",
    "integration_operation",
    "integration_field",
  ]) {
    if (!model.includes(`__tablename__ = \"${table}\"`)) {
      issues.push(`models/integration.py: ${table} table is required`);
    }
  }
  if (/config_revision/.test(model)) {
    issues.push(
      "models/integration.py: config_revision is outside the live-configuration standard",
    );
  }
  // A secret is a named row owned by the provider, resolved through a field FK.
  // Storing the value on the field row loses it whenever fields are replaced.
  if (!/class IntegrationSecret\b/.test(model) || !/secret_id/.test(model)) {
    issues.push(
      "models/integration.py: named secrets require IntegrationSecret plus a field secret_id FK",
    );
  }
  if (/\b(secret_ref|secret_value|literal_value|default_value|source_key)\b/.test(model)) {
    issues.push(
      "models/integration.py: sparse value columns are replaced by value + secret_id",
    );
  }
  if (!/response_root/.test(model)) {
    issues.push(
      "models/integration.py: response_root defines the response contract — absent maps a " +
        "record, present maps every element of the page it names",
    );
  }
  if (/response_mode/.test(model)) {
    issues.push(
      "models/integration.py: response_mode is removed — mapping is the only response " +
        "contract, so a mode column carries one legal value",
    );
  }
  if (/response_schema/.test(model)) {
    issues.push(
      "models/integration.py: response_schema duplicated the response field rows — removed",
    );
  }

  const schema = readFileSync(schemaPath, "utf-8");
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
  // Class ordering: request-side before response-side before update-side,
  // then standalone request/response pairs, then to_read helpers last.
  const order = [
    "IntegrationSecretCreateRequest",
    "IntegrationFieldCreateRequest",
    "IntegrationOperationCreateRequest",
    "IntegrationCreateRequest",
    "IntegrationCreateInternal",
    "IntegrationSecretReadResponse",
    "IntegrationFieldReadResponse",
    "IntegrationOperationReadResponse",
    "IntegrationReadResponse",
    "IntegrationUpdateRequest",
    "IntegrationUpdateInternal",
    "IntegrationExecuteRequest",
    "IntegrationExecuteResponse",
  ];
  let lastIndex = -1;
  for (const cls of order) {
    const index = schemaClasses.indexOf(cls);
    if (index === -1) {
      issues.push(`schemas/integration.py: required class ${cls} is missing`);
      continue;
    }
    if (index < lastIndex) {
      issues.push(
        `schemas/integration.py: class ${cls} is out of order — ` +
          "request-side, then response-side, then update-side, then execute pairs",
      );
    }
    lastIndex = index;
  }
  if (schemaClasses.indexOf("to_read") !== -1) {
    issues.push("schemas/integration.py: to_read is a function, not a class");
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

  const repository = readFileSync(repositoryPath, "utf-8");
  if (
    !/async def get_operation\(/.test(repository) ||
    !/selectinload\(IntegrationOperation/.test(repository)
  ) {
    issues.push(
      "repositories/integration.py: operation resolution must eager-load configuration children",
    );
  }

  const service = readFileSync(servicePath, "utf-8");
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
  if (
    !/prefix=\"\/integration\"/.test(router) ||
    !/IntegrationServiceDep/.test(router)
  ) {
    issues.push(
      "routers/integration.py: authenticated integration configuration CRUD is required",
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
      "models/integration.py: integration_operation.response_format (JSON|XML) is required",
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
