// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
// @ts-expect-error — Node builtin, not project-compiled
import { join } from "node:path";

/**
 * Domain structure checks — 5-layer CRUD pattern (backend-domain.md).
 *
 * Validates:
 *   - model filename format (<name>.py, lowercase alphanumeric)
 *   - data chain existence (model → schema → repository → service; router optional)
 *   - file contents per layer (model/schema/repository/service/router/DI/main/env)
 *
 * Pure validation — no ast-grep, no side effects. Called by the
 * check-backend-domain orchestrator.
 */

const cwd = process.cwd();
const projectRoot = existsSync(join(cwd, "backend", "app")) ? cwd : join(cwd, "..");

/**
 * Under asyncio there is no safe lazy default: a relationship touched outside a
 * loaded query raises `MissingGreenlet` from deep inside greenlet plumbing, at
 * whichever endpoint happens to touch it first. `lazy="raise_on_sql"` moves that
 * failure to the access itself with a sentence a reader can act on, and makes
 * the eager-load contract enforceable by the runtime instead of by review.
 */
export function checkRelationshipLoading(base: string): string[] {
  const issues: string[] = [];
  const modelsDir = join(base, "models");
  if (!existsSync(modelsDir)) return issues;

  for (const file of readdirSync(modelsDir)) {
    if (!file.endsWith(".py")) continue;
    const source = readFileSync(join(modelsDir, file), "utf-8");
    const lines = source.split("\n");
    lines.forEach((line: string, index: number) => {
      if (!/=\s*relationship\(/.test(line)) return;
      // The call may span lines; read to its closing parenthesis.
      let call = line;
      for (let next = index + 1; next < lines.length && !/\)\s*$/.test(call); next++) {
        call += `\n${lines[next]}`;
      }
      if (/lazy=/.test(call)) return;
      const name = (/^\s*(\w+)/.exec(line) ?? [])[1] ?? "relationship";
      issues.push(
        `models/${file}:${index + 1}: ${name} declares no \`lazy=\` policy — ` +
          'under asyncio use lazy="raise_on_sql" so a forgotten eager load fails at the ' +
          "access instead of raising MissingGreenlet in production",
      );
    });
  }
  return issues;
}

/**
 * Domains that own more than one model file — a multi-table aggregate, checked
 * by its own file-shape hooks (check-backend-model-files,
 * check-backend-repository-files) and, when one exists, its dedicated
 * configuration hook, never by the generic single-resource CRUD template every
 * other hook in this file assumes.
 *
 * **Structural, not named.** Hardcoding a domain's name to skip it is what
 * broke three times in one session when `integration.py` became five files:
 * `check-backend-transaction`'s own `file !== "integration.py"` filter,
 * `check-backend-tests`'s own `Set(["integration"])`, and this file's earlier
 * `name === "integration"` skip all stopped matching anything the day the
 * split landed, because none of them asked "does this domain own more than one
 * file" — they asked "is this domain literally named integration". A domain
 * discovered this way needs no update when the next aggregate is split; a
 * hardcoded name needs one every time, silently, until someone happens to
 * touch that exact domain again.
 *
 * Measured two ways, because the aggregate has two shapes: several model files
 * (the folder), or one flat file declaring several tables — the shape a domain
 * has before its folder move, and the shape the sandbox baseline keeps.
 */
export function aggregateDomains(): Set<string> {
  const base = join(projectRoot, "backend", "app");
  const serviceDir = join(base, "services");
  if (!existsSync(join(base, "models")) || !existsSync(serviceDir)) return new Set();

  const result = new Set<string>();
  for (const name of listDomains(serviceDir)) {
    if (ownedModelFiles(name).length > 1 || ownedTableCount(name) > 1) result.add(name);
  }
  return result;
}

/**
 * The model files one domain owns, in either shape:
 *
 * - `models/<domain>/*.py` - a folder, required once a domain owns more than
 *   one table (`backend-model-files.md`). The file inside is named after its
 *   table with the domain prefix dropped, so `integration/provider.py` maps
 *   `integration_provider`.
 * - `models/<domain>.py`, or the flat `models/<domain>_*.py` a domain has
 *   while it is being moved into a folder.
 *
 * Returned as paths relative to `models/`, because a caller that only ever saw
 * bare filenames was the reason the folder move went unnoticed: five files
 * moved one directory down, `readdirSync` stopped matching them, and every
 * aggregate check silently reported success on nothing.
 */
export function ownedModelFiles(domain: string): string[] {
  const modelDir = join(projectRoot, "backend", "app", "models");
  if (!existsSync(modelDir)) return [];

  const folder = join(modelDir, domain);
  if (existsSync(folder) && statSync(folder).isDirectory()) {
    return readdirSync(folder)
      .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
      .map((f: string) => `${domain}/${f}`);
  }

  return readdirSync(modelDir).filter(
    (f: string) => f === `${domain}.py` || (f.startsWith(`${domain}_`) && f.endsWith(".py")),
  );
}

/**
 * `__tablename__` declarations across the model files one domain owns — the
 * other half of the aggregate measure. A flat `models/<domain>.py` that maps
 * four tables is exactly as much an aggregate as four files in a folder, and
 * the singular one-table templates fit it exactly as badly.
 */
export function ownedTableCount(domain: string): number {
  const modelDir = join(projectRoot, "backend", "app", "models");
  let count = 0;
  for (const file of ownedModelFiles(domain)) {
    const source = readFileSync(join(modelDir, file), "utf-8");
    count += (source.match(/^\s*__tablename__\s*=/gm) ?? []).length;
  }
  return count;
}

/** Domain names, from the layer that decides a domain exists: `services/`. */
export function listDomains(serviceDir: string): string[] {
  if (!existsSync(serviceDir)) return [];
  const names: string[] = [];
  for (const entry of readdirSync(serviceDir, { withFileTypes: true })) {
    if (entry.name === "__init__.py" || entry.name === "__pycache__") continue;
    if (entry.isDirectory()) names.push(entry.name);
    else if (entry.name.endsWith(".py")) names.push(entry.name.replace(".py", ""));
  }
  return names;
}

/** True when `stem` (a filename minus `.py`) belongs to a multi-file domain. */
export function belongsToAggregateDomain(stem: string, aggregates: Set<string>): boolean {
  for (const domain of aggregates) {
    if (stem === domain || stem.startsWith(`${domain}_`)) return true;
  }
  return false;
}

/**
 * Every `.py` under a layer directory, one level deep, as paths relative to
 * it: `user.py`, `integration/provider.py`. One level is the whole convention -
 * a domain folder holds table files, never more folders.
 */
export function listModelFiles(layerDir: string): string[] {
  if (!existsSync(layerDir)) return [];
  const files: string[] = [];
  for (const entry of readdirSync(layerDir, { withFileTypes: true })) {
    if (entry.name === "__pycache__" || entry.name === "__init__.py") continue;
    if (entry.isDirectory()) {
      for (const inner of readdirSync(join(layerDir, entry.name))) {
        if (inner.endsWith(".py") && inner !== "__init__.py") files.push(`${entry.name}/${inner}`);
      }
    } else if (entry.name.endsWith(".py")) {
      files.push(entry.name);
    }
  }
  return files;
}

/**
 * One domain's source in a layer, as a single string: the file when the layer
 * holds `<domain>.py`, the concatenation of `<domain>/*.py` when the domain has
 * grown into a folder.
 *
 * Concatenating is what makes the split invisible to a content check. The
 * alternative - picking one file - is how a check starts reading half a
 * contract and passing: `schemas/integration/provider.py` alone has no
 * `IntegrationSecretCreateRequest`, and the domain's schema contract is the
 * whole folder.
 */
export function readLayerSource(layerDir: string, domain: string): string | null {
  const file = join(layerDir, `${domain}.py`);
  if (existsSync(file)) return readFileSync(file, "utf-8");

  const folder = join(layerDir, domain);
  if (!existsSync(folder) || !statSync(folder).isDirectory()) return null;
  return readdirSync(folder)
    .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
    .sort()
    .map((f: string) => readFileSync(join(folder, f), "utf-8"))
    .join("\n");
}

/**
 * Absolute paths of the files one domain owns in a layer - the folder's
 * contents, or the flat `<domain>.py` / `<domain>_*.py` files.
 */
export function listDomainLayerFiles(layerDir: string, domain: string): string[] {
  if (!existsSync(layerDir)) return [];

  const folder = join(layerDir, domain);
  if (existsSync(folder) && statSync(folder).isDirectory()) {
    return readdirSync(folder)
      .filter((f: string) => f.endsWith(".py") && f !== "__init__.py")
      .sort()
      .map((f: string) => join(folder, f));
  }

  return readdirSync(layerDir)
    .filter((f: string) => f === `${domain}.py` || (f.startsWith(`${domain}_`) && f.endsWith(".py")))
    .sort()
    .map((f: string) => join(layerDir, f));
}

/**
 * A layer must not hold both `<domain>.py` and `<domain>/` for the same domain.
 *
 * Measured: with `models/user.py` and `models/user/extra.py` both present,
 * every check passed. `ownedModelFiles()` answers with the folder and stops
 * looking, so the flat file's table was invisible - the exact shape a
 * half-finished move leaves behind, and the one state where "which files does
 * this domain own" has two answers.
 */
export function checkLayerOwnership(layerDir: string, layerLabel: string): string[] {
  if (!existsSync(layerDir)) return [];
  const issues: string[] = [];
  for (const entry of readdirSync(layerDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === "__pycache__") continue;
    if (!existsSync(join(layerDir, `${entry.name}.py`))) continue;
    issues.push(
      `${layerLabel}/: ${entry.name} owns both ${entry.name}.py and ${entry.name}/ - ` +
        "a domain lives in one or the other; finish the move and delete the flat file",
    );
  }
  return issues;
}

export function checkDomainStructure(): string[] {
  const issues: string[] = [];
  const base = join(projectRoot, "backend", "app");
  const modelDir = join(base, "models");
  const schemaDir = join(base, "schemas");
  const repoDir = join(base, "repositories");
  const serviceDir = join(base, "services");
  const routerDir = join(base, "routers");
  const mainPy = join(base, "main.py");
  const envPy = join(projectRoot, "backend", "alembic", "env.py");

  if (!existsSync(modelDir)) {
    issues.push("backend/app/models/ directory not found");
    return issues;
  }

  // No layer may answer "which files does this domain own" two ways at once.
  for (const [dir, label] of [
    [modelDir, "models"],
    [schemaDir, "schemas"],
    [repoDir, "repositories"],
    [serviceDir, "services"],
  ] as const) {
    issues.push(...checkLayerOwnership(dir, label));
  }

  // A domain is a 5-layer stack, and the layer that decides one exists is the
  // service. Discovery used to enumerate **model files**, which made a table
  // and a domain the same thing - so `integration` had to be skipped by name,
  // and the moment one table moved to its own file the checker demanded a
  // router, a schema and a service for `integration_secret`.
  //
  // One table per model file is the table rule (`backend-model-files.md`), and
  // a domain that owns several of them keeps them in `models/<domain>/`. Both
  // shapes are read through `ownedModelFiles()` so this checker, the aggregate
  // predicate, and the file-shape hooks cannot disagree about what a domain
  // owns - they disagreed once already, and the answer was silence.
  const modelFiles: string[] = listModelFiles(modelDir);

  // File naming: lower snake case, because a model file is named after its
  // table (minus the domain prefix when it sits in the domain's folder).
  for (const modelFile of modelFiles) {
    const name = modelFile.replace(/^.*\//, "").replace(".py", "");
    if (!/^[a-z][a-z0-9_]*$/.test(name)) {
      issues.push(
        `${modelFile}: model filename must be lower snake case - it is named after ` +
          "the table it maps (backend-model-files.md)",
      );
    }
  }

  const domains: string[] = listDomains(serviceDir);

  const repoFiles: string[] = existsSync(repoDir) ? listModelFiles(repoDir) : [];

  for (const name of domains) {
    const cls = name.charAt(0).toUpperCase() + name.slice(1);

    const owned = ownedModelFiles(name);
    if (owned.length === 0) {
      issues.push(
        `${name}: services layer exists but no model file ` +
          `(models/${name}.py, models/${name}/*.py, or models/${name}_*.py)`,
      );
      continue;
    }
    const modelFile = owned.includes(`${name}.py`) ? `${name}.py` : owned.sort()[0];
    // A model file per table (backend-model-files.md), so a domain's repository
    // side is not required to be exactly `repositories/<name>.py` either - only
    // that at least one file exists for it, in the folder when there are
    // several (`backend-repository-files.md`).
    const ownedRepos = repoFiles.filter(
      (file: string) =>
        file === `${name}.py` || file.startsWith(`${name}_`) || file.startsWith(`${name}/`),
    );
    // The singular templates below (model class == domain name, repository's
    // 7-method shape) describe one table's worth of CRUD. A domain that owns
    // several files — several tables, several repositories — is checked by its
    // own file-shape hooks (check-backend-model-files,
    // check-backend-repository-files) and its dedicated configuration hook when
    // one exists; running the singular template against an arbitrarily chosen
    // file here is what let `models/integration_call.py` satisfy `model class
    // "Integration" not found` by prefix coincidence (`IntegrationCall` starts
    // with `Integration`) before this gate existed.
    // The aggregate is measured, never named (see aggregateDomains): several
    // model files, or one flat file declaring several tables. Either shape puts
    // the domain outside the one-table templates below.
    const isAggregate = owned.length > 1 || ownedTableCount(name) > 1;
    const isSingleFileDomain = !isAggregate && owned.length === 1 && owned[0] === `${name}.py`;
    const isSingleRepoDomain = !isAggregate && ownedRepos.length === 1 && ownedRepos[0] === `${name}.py`;

    // Data chain: model → schema → repository → service. Router is OPTIONAL —
    // a domain may be internal-only (batch jobs) or exposed via a custom
    // router (auth). When a router exists, its content is validated below.
    //
    // 완성도 요구는 **의존 방향으로만** 건다(2026-08-29 사용자 지적 + 실측). 도메인 발견 자체가
    // services/ 앵커라서 모델만(또는 모델+스키마만) 있는 상태는 도메인으로 잡히지 않는다 — 작업의
    // 첫 걸음에서 마지막 걸음을 요구하지 않는다. 여기 도달한 도메인은 서비스(또는 라우터)가 이미
    // 섰으므로 그 하류가 상류(schema·repository)를 요구한다. 완성 시점의 계약은 그대로다.
    const routerPath = join(routerDir, `${name}.py`);
    const hasRouter = existsSync(routerPath);
    const anchor = hasRouter ? "routers" : "services";
    const schemaSource = readLayerSource(schemaDir, name);
    if (schemaSource === null) {
      issues.push(
        `${name}: ${anchor} layer exists but schema layer is missing ` +
          `(schemas/${name}.py or schemas/${name}/*.py)`,
      );
    }
    if (ownedRepos.length === 0) {
      issues.push(
        `${name}: ${anchor} layer exists but repository layer is missing ` +
          `(repositories/${name}.py, repositories/${name}/*.py, or repositories/${name}_*.py)`,
      );
    }
    if (readLayerSource(serviceDir, name) === null) {
      // premature-ok: services/ 가 이 도메인을 선언했는데 읽을 소스가 없다 — 어느 단계에서든 결함이다.
      issues.push(`${name}: missing service file (services/${name}.py or services/${name}/*.py)`);
    }

    // --- Validate file contents ---

    const modelPath = join(modelDir, modelFile);
    const modelContent = readFileSync(modelPath, "utf-8");

    if (isSingleFileDomain) {
      // Model: should have Base, AuditMixin, UUID id, name/description
      if (!modelContent.includes("AuditMixin")) {
        issues.push(`${name}: model missing AuditMixin`);
      }
      if (!modelContent.includes("class " + cls)) {
        issues.push(`${name}: model class "${cls}" not found`);
      }
      if (!modelContent.includes("Mapped[uuid.UUID]")) {
        issues.push(`${name}: model id must be Mapped[uuid.UUID] (UUID primary key)`);
      }
      if (!modelContent.includes("default=uuid4")) {
        issues.push(`${name}: model id missing default=uuid4`);
      }
      if (!modelContent.includes("mapped_column")) {
        issues.push(`${name}: model missing mapped_column`);
      }
      if (!new RegExp(`__tablename__ = "${name}"`).test(modelContent)) {
        issues.push(`${name}: ${modelFile} must declare __tablename__ "${name}"`);
      }
    }

    // Schema: should have 6 classes, extra="forbid"
    // Naming convention: XBase, XCreateRequest, XCreateInternal, XReadResponse,
    // XUpdateRequest, XUpdateInternal (Request/Response suffixes).
    if (schemaSource !== null) {
      const schemaContent = schemaSource;
      const expected = [
        `${cls}Base`,
        `${cls}CreateRequest`,
        `${cls}CreateInternal`,
        `${cls}ReadResponse`,
        `${cls}UpdateRequest`,
        `${cls}UpdateInternal`,
      ];
      for (const c of expected) {
        if (!new RegExp(`class\\s+${c}\\b`).test(schemaContent)) {
          issues.push(`${name}: schema missing class ${c}`);
        }
      }

      // Per class, not per file: one new schema class without extra="forbid"
      // silently accepts unknown request fields while its siblings reject them.
      for (const declaration of schemaContent.matchAll(
        /^class\s+(\w+)\((?:BaseModel|\w+)\):\n((?:[ \t].*\n|\n)*)/gm,
      )) {
        const [, className, classBody] = declaration;
        if (!/model_config\s*=\s*ConfigDict\(/.test(classBody)) continue;
        if (!/extra=["']forbid["']/.test(classBody)) {
          issues.push(`${name}: schema class ${className} missing extra="forbid"`);
        }
      }
      if (!schemaContent.includes("from_attributes=True")) {
        issues.push(`${name}: schema Read missing from_attributes=True`);
      }
      if (!schemaContent.includes("def to_read(") || !schemaContent.includes("def to_read_list(")) {
        issues.push(`${name}: schema missing to_read()/to_read_list() helpers`);
      }
      if (!schemaContent.includes("id: UUID")) {
        issues.push(`${name}: schema Read missing id: UUID`);
      }
      // The optimistic-lock counter is only usable by a client that can read it.
      if (!/^\s+version:\s*int/m.test(schemaContent)) {
        issues.push(
          `${name}: schema Read missing version: int — clients cannot observe the ` +
            "optimistic-lock revision they hold",
        );
      }
    }

    // Repository: should have 7 methods, UUID id params — the single-table
    // template. A domain with several repository files is checked structurally
    // by check-backend-repository-files instead (backend-repository-files.md).
    const repoPath = join(repoDir, `${name}.py`);
    if (isSingleRepoDomain && existsSync(repoPath)) {
      const repoContent = readFileSync(repoPath, "utf-8");
      const methods = ["async def get", "async def list", "async def find_stale", "async def create", "async def update", "async def delete", "def __init__"];
      for (const method of methods) {
        if (!repoContent.includes(method)) {
          issues.push(`${name}: repository missing method "${method.replace("async def ", "").replace("def ", "")}"`);
        }
      }
      if (!repoContent.includes(`${name}_id: UUID`)) {
        issues.push(`${name}: repository id params must be typed UUID (${name}_id: UUID)`);
      }
      if (!repoContent.includes("created_at < older_than")) {
        issues.push(`${name}: repository find_stale must filter by created_at < older_than`);
      }
    }

    // Service: should have session.begin() transaction management and NotFoundError
    const servicePath = join(serviceDir, `${name}.py`);
    if (existsSync(servicePath)) {
      const serviceContent = readFileSync(servicePath, "utf-8");
      if (!serviceContent.includes("session.begin()")) {
        issues.push(`${name}: service missing session.begin() transaction management`);
      }
      if (!serviceContent.includes("NotFoundError")) {
        issues.push(`${name}: service missing NotFoundError`);
      }
      if (!serviceContent.includes(`${name}_id: UUID`)) {
        issues.push(`${name}: service id params must be typed UUID (${name}_id: UUID)`);
      }
      if (!serviceContent.includes("exclude_unset=True")) {
        issues.push(`${name}: service update must use exclude_unset=True`);
      }
      // `updated_at` belongs to the repository, set before its flush. A service
      // assignment lands after the flush and costs a second UPDATE, which bumps
      // the optimistic-lock version twice per request.
      if (/\.updated_at\s*=/.test(serviceContent)) {
        issues.push(
          `${name}: service must not assign updated_at — set it in the repository ` +
            "before flush (a post-flush assignment costs a second UPDATE and version bump)",
        );
      }
    }

    // Router: should have 5 endpoints, UUID path params
    if (hasRouter) {
      const routerContent = readFileSync(routerPath, "utf-8");
      if (!routerContent.includes("@router.post")) {
        issues.push(`${name}: router missing POST endpoint`);
      }
      if (!routerContent.includes("@router.get")) {
        issues.push(`${name}: router missing GET endpoint`);
      }
      // update 메서드는 스키마 의미가 정한다(PATCH=부분 갱신 / PUT=전체 교체) — 어느 쪽인지의
      // 판정은 check-backend-api-http 의 expectedUpdateMethod 소관이고, 여기서는 존재만 본다.
      if (!routerContent.includes("@router.patch") && !routerContent.includes("@router.put")) {
        issues.push(`${name}: router missing update endpoint (PATCH or PUT — the verb follows the update schema, rule://backend-api-http)`);
      }
      if (!routerContent.includes("@router.delete")) {
        issues.push(`${name}: router missing DELETE endpoint`);
      }
      if (!routerContent.includes(`${name}_id: UUID`)) {
        issues.push(`${name}: router path params must be typed UUID (${name}_id: UUID)`);
      }
      if (!routerContent.includes(`prefix="/${name}"`)) {
        issues.push(`${name}: router prefix must be "/${name}" (lowercase domain name)`);
      }
    }

    // Env: every one of the domain's model files must be imported. Per file, not
    // per domain: a table nobody imports is absent from the metadata, so
    // autogenerate writes an empty migration and the table never exists.
    if (existsSync(envPy)) {
      const envContent = readFileSync(envPy, "utf-8");
      for (const file of owned) {
        // `integration/provider.py` is the module `integration.provider`: the
        // folder is a package, so the import path carries a dot, not a slash.
        // `[\w(]` accepts the parenthesized multi-line form a four-table flat
        // module imports with — `import (` is as much a registration as `import X`.
        const module = file.replace(/\.py$/, "").split("/").join(".");
        if (!new RegExp(`from app\\.models\\.${module} import\\s*[\\w(]`).test(envContent)) {
          // premature-ok: autogenerate 는 import 없는 모델을 보지 못한다 — 이 등록은 모델 자체의 속성이다.
          issues.push(`${module}: not imported in alembic/env.py`);
        }
      }
    }

    // Main: 라우터 등록은 **라우터 파일이 생긴 뒤**에만 요구한다(2026-08-29).
    // 모델만 만든 상태에서 "router not included" 를 띄우는 것은 첫 걸음에서 마지막 걸음을 요구하는 것이다.
    if (hasRouter && existsSync(mainPy)) {
      const mainContent = readFileSync(mainPy, "utf-8");
      const routerRegistration = new RegExp(`include_router\\(${name}\\.router(?:,|\\))`);
      if (!routerRegistration.test(mainContent)) {
        issues.push(`${name}: router not included in main.py`);
      }
    }

    // Dependencies: service DI must exist (SessionDep -> ServiceDep). A domain
    // whose service layer is a folder has one service per file, so it needs one
    // factory and one Annotated alias per file - not one named after the domain,
    // which no longer exists as a class once the service is split.
    const depsServicesPath = join(base, "dependencies", "services.py");
    if (existsSync(depsServicesPath)) {
      const depsContent = readFileSync(depsServicesPath, "utf-8");
      const serviceFiles = listDomainLayerFiles(serviceDir, name);
      const isFolder = serviceFiles.some((file) => file.includes(`${name}/`));
      const parts = isFolder
        ? serviceFiles.map((file) => {
            const leaf = (file.split("/").pop() ?? "").replace(/\.py$/, "");
            const leafCls = leaf.charAt(0).toUpperCase() + leaf.slice(1);
            return { factory: `get_${name}_${leaf}_service`, cls: `${cls}${leafCls}Service` };
          })
        : [{ factory: `get_${name}_service`, cls: `${cls}Service` }];
      for (const part of parts) {
        if (!depsContent.includes(part.factory)) {
          issues.push(`${name}: missing ${part.factory} in dependencies/services.py`);
        }
        if (!new RegExp(`${part.cls}Dep\\s*=\\s*Annotated\\[\\s*${part.cls}`).test(depsContent)) {
          issues.push(`${name}: missing ${part.cls}Dep Annotated DI in dependencies/services.py`);
        }
      }
    } else {
      // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
      issues.push(`${name}: dependencies/services.py not found`);
    }
  }

  return issues;
}
