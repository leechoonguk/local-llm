/**
 * Strict-Backend-App-Structure Pre Hook
 *
 * Enforces the documented backend folder structure (backend-domain.md):
 * files may only be created inside recognized locations. Anything else —
 * a new directory under backend/, or a stray file outside the structure —
 * is blocked at write/edit time.
 *
 * Recognized locations:
 *   - backend/app/<allowedDir>/...  (models, schemas, repositories, services,
 *     routers, dependencies, core, batch, tests)
 *   - backend/app/main.py, backend/app/__init__.py (app root files only)
 *   - backend/tests/, backend/alembic/, backend/scripts/ (standard backend dirs)
 *
 * Blocked:
 *   - backend/app/<unknownDir>/...     — new directory under app/ (e.g. adapters/)
 *   - backend/app/<stray>.py           — loose file at app root (only main.py
 *     and __init__.py are allowed)
 *   - backend/<unknownDir>/...         — new directory under backend/ outside the
 *     standard set (e.g. backend/api/, backend/workers/)
 *
 * To add/remove directories: edit the allowlists below. No other logic changes.
 */
const allowedAppDirs: Record<string, true> = {
  models: true,
  schemas: true,
  repositories: true,
  services: true,
  routers: true,
  dependencies: true,
  core: true,
  batch: true,
  tests: true,
};

const allowedBackendDirs: Record<string, true> = {
  app: true,
  tests: true,
  alembic: true,
  scripts: true,
};

const allowedAppRootFiles: Record<string, true> = {
  "main.py": true,
  "__init__.py": true,
};

export default function strictBackendAppStructure(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: { toolName: string; input: Record<string, unknown> }, _ctx: unknown) => {
    if (event.toolName !== "write" && event.toolName !== "edit") return;

    const path = String((event.input as Record<string, unknown>)?.path ?? "");

    // backend/app/<subdir>/... — known app subdirectories only.
    const appMatch = path.match(/(?:^|\/)backend\/app\/([^/]+)\//);
    if (appMatch) {
      const subdir = appMatch[1];
      if (!allowedAppDirs[subdir]) {
        return {
          block: true,
          reason: `\`${subdir}\` — backend/app/ 하위에 새 디렉토리 생성 금지\n\n기존 구조만 사용하세요:\n  models, schemas, repositories, services, routers,\n  dependencies, core, batch, tests`,
        };
      }
      return;
    }

    // backend/app/<file> — only main.py and __init__.py live at the app root.
    const appFileMatch = path.match(/(?:^|\/)backend\/app\/([^/]+)$/);
    if (appFileMatch) {
      const file = appFileMatch[1];
      if (!allowedAppRootFiles[file]) {
        return {
          block: true,
          reason: `\`backend/app/${file}\` — app 루트에는 main.py와 __init__.py만 허용\n\n모듈은 표준 디렉토리 안에 두세요:\n  models, schemas, repositories, services, routers,\n  dependencies, core, batch, tests`,
        };
      }
      return;
    }

    // backend/<subdir>/... — standard backend directories only.
    const backendMatch = path.match(/(?:^|\/)backend\/([^/]+)\//);
    if (backendMatch) {
      const subdir = backendMatch[1];
      if (!allowedBackendDirs[subdir]) {
        return {
          block: true,
          reason: `\`backend/${subdir}\` — backend/ 하위 비표준 위치 생성 금지\n\n인정 위치만 사용하세요:\n  app, tests, alembic, scripts\n\n(.http 파일은 저장소 루트 api/ 디렉토리)`,
        };
      }
    }
  });
}
