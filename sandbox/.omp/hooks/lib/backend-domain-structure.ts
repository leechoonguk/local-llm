// @ts-expect-error — Node builtin, not project-compiled
import { existsSync, readdirSync, readFileSync } from "node:fs";
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

  const modelFiles: string[] = [];
  for (const f of readdirSync(modelDir)) {
    if (f.endsWith(".py") && f !== "__init__.py") {
      modelFiles.push(f);
    }
  }

  // File naming: <name>.py must be lowercase alphanumeric — the model file
  // name is the single source of truth for the domain name, and the other
  // 4 layers must use the same <name>.py (checked below).
  for (const modelFile of modelFiles) {
    const name = modelFile.replace(".py", "");
    if (!/^[a-z][a-z0-9]*$/.test(name)) {
      issues.push(
        `${modelFile}: model filename must be <name>.py (lowercase alphanumeric) — ` +
          "it defines the domain name used by schemas/repositories/services/routers",
      );
    }
  }

  for (const modelFile of modelFiles) {
    const name = modelFile.replace(".py", "");
    const cls = name.charAt(0).toUpperCase() + name.slice(1);

    // Skip only models that are not CRUD domains. `base` holds the declarative
    // base and mixins; `integration` is a configuration aggregate with its own
    // four-table contract in check-backend-integration-configuration. Every
    // other model — including `batch` — must satisfy the 5-layer contract, or
    // deleting a sample domain silently empties this check.
    if (name === "base" || name === "integration") continue;

    // 완성도 요구는 **의존 방향으로만** 건다(2026-08-29 사용자 지적 + 실측).
    // 예전에는 모델 파일 하나가 생기는 순간 schema/repository/service 누락 3건을 지적했다 —
    // 즉 작업의 첫 걸음에서 마지막 걸음을 요구한 셈이다. 실측에서 이 목록이 모델에게 작업 큐로
    // 읽혔고("첫 실패 수정 완료. 다음: missing service file"), 사용자가 한 계층만 요청한
    // 프롬프트를 기능 전체로 부풀리는 주된 압력이었다.
    //
    // 새 규칙: 존재하는 **가장 하류 계층**이 그 상류를 요구한다. 라우터가 있으면 서비스·리포지토리·
    // 스키마가 있어야 하고, 서비스가 있으면 리포지토리·스키마가, 리포지토리가 있으면 스키마가
    // 있어야 한다. 모델만(또는 모델+스키마만) 있는 상태는 완성 전 단계이지 위반이 아니다.
    // 완성 시점의 계약은 그대로다 — 라우터가 서면 5계층이 전부 강제된다.
    const hasSchema = existsSync(join(schemaDir, `${name}.py`));
    const hasRepo = existsSync(join(repoDir, `${name}.py`));
    const hasService = existsSync(join(serviceDir, `${name}.py`));
    const hasRouter = existsSync(join(routerDir, `${name}.py`));
    const required = hasRouter
      ? ["schema", "repository", "service"]
      : hasService
        ? ["schema", "repository"]
        : hasRepo
          ? ["schema"]
          : [];
    const anchor = hasRouter ? "routers" : hasService ? "services" : "repositories";
    for (const layer of required) {
      const [dir, present] = layer === "schema"
        ? [schemaDir, hasSchema]
        : layer === "repository"
          ? [repoDir, hasRepo]
          : [serviceDir, hasService];
      if (!present) {
        issues.push(`${name}: ${anchor}/${name}.py exists but ${layer} file is missing (${(dir as string).split("/").pop()}/${name}.py)`);
      }
    }

    // --- Validate file contents ---

    const modelPath = join(modelDir, modelFile);
    const modelContent = readFileSync(modelPath, "utf-8");

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
    if (!modelContent.includes(`__tablename__ = "${name}"`)) {
      issues.push(`${name}: model __tablename__ must be "${name}" (lowercase domain name)`);
    }

    // Schema: should have 6 classes, extra="forbid"
    // Naming convention: XBase, XCreateRequest, XCreateInternal, XReadResponse,
    // XUpdateRequest, XUpdateInternal (Request/Response suffixes).
    const schemaPath = join(schemaDir, `${name}.py`);
    if (existsSync(schemaPath)) {
      const schemaContent = readFileSync(schemaPath, "utf-8");
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

    // Repository: should have 7 methods, UUID id params
    const repoPath = join(repoDir, `${name}.py`);
    if (existsSync(repoPath)) {
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
    const routerPath = join(routerDir, `${name}.py`);
    if (existsSync(routerPath)) {
      const routerContent = readFileSync(routerPath, "utf-8");
      if (!routerContent.includes("@router.post")) {
        issues.push(`${name}: router missing POST endpoint`);
      }
      if (!routerContent.includes("@router.get")) {
        issues.push(`${name}: router missing GET endpoint`);
      }
      if (!routerContent.includes("@router.put")) {
        issues.push(`${name}: router missing PUT endpoint`);
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

    // Env: model must be imported
    if (existsSync(envPy)) {
      const envContent = readFileSync(envPy, "utf-8");
      if (!new RegExp(`from app\\.models\\.${name} import\\s+\\w+`).test(envContent)) {
        // premature-ok: autogenerate 는 import 없는 모델을 보지 못한다 — 이 등록은 모델 자체의 속성이다.
        issues.push(`${name}: not imported in alembic/env.py`);
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

    // Dependencies: 서비스 DI 는 **서비스 파일이 생긴 뒤**에만 요구한다(같은 이유).
    const depsServicesPath = join(base, "dependencies", "services.py");
    if (!existsSync(depsServicesPath)) {
      // premature-ok: 프로젝트 기반 파일의 부재는 작업 순서가 아니라 설정 결함이다 — 어느 단계에서든 참이다.
      issues.push(`${name}: dependencies/services.py not found`);
    } else if (hasService) {
      const depsContent = readFileSync(depsServicesPath, "utf-8");
      if (!depsContent.includes(`get_${name}_service`)) {
        issues.push(`${name}: missing get_${name}_service in dependencies/services.py`);
      }
      if (!new RegExp(`${cls}ServiceDep\\s*=\\s*Annotated\\[${cls}Service`).test(depsContent)) {
        issues.push(`${name}: missing ${cls}ServiceDep Annotated DI in dependencies/services.py`);
      }
    }
  }

  return issues;
}
