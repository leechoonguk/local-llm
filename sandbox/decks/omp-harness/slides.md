---
marp: true
theme: einstein
paginate: true
header: "우리 하네스 (OMP) 소개"
footer: "FastAPI Standard — OMP Harness"
style: |
  section {
    font-size: 24px;
  }
  h1 {
    font-size: 1.8em;
  }
  h2 {
    font-size: 1.3em;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2em;
  }
  .columns ul {
    margin-top: 0.5em;
  }
  .lead {
    text-align: center;
    font-size: 1.4em;
    font-weight: bold;
    margin-top: 1.5em;
  }
  .muted {
    font-size: 0.85em;
  }
  .center {
    text-align: center;
  }
  code {
    font-size: 0.85em;
  }
---
<!-- sync: backend-api-http.md=4f875edfe82e8016 -->
<!-- sync: backend-api-keys.md=240f10d0c15e7197 -->
<!-- sync: backend-app-forbidden-tokens.md=ea8d74690ce51928 -->
<!-- sync: backend-app-setup.md=17d665e697444fd2 -->
<!-- sync: backend-audit-log.md=8ff51ab42272c7b2 -->
<!-- sync: backend-auth.md=96c341a1d5492ff5 -->
<!-- sync: backend-background-tasks.md=f44f5777655cd583 -->
<!-- sync: backend-batch.md=32883d17939efb3a -->
<!-- sync: backend-code-conventions.md=0bf48fdb99b9c4f1 -->
<!-- sync: backend-contract.md=49daf5deab1bf01f -->
<!-- sync: backend-core-config.md=2df96e9e761e6fea -->
<!-- sync: backend-domain.md=6afbb265afa24861 -->
<!-- sync: backend-exceptions.md=f553445ca7629751 -->
<!-- sync: backend-file-upload.md=417dc0174bf98a36 -->
<!-- sync: backend-identity-tokens.md=1bbcce7b00ea655c -->
<!-- sync: backend-integration-configuration.md=022f9ee019c4eae3 -->
<!-- sync: backend-integration.md=f9cd0a15ed9ea08c -->
<!-- sync: backend-makefile.md=7f10901469427649 -->
<!-- sync: backend-middleware.md=0b9ef780cf382b33 -->
<!-- sync: backend-migrations.md=a78b3fbce29897f8 -->
<!-- sync: backend-model-files.md=b2c5f76dc38e3ed2 -->
<!-- sync: backend-naming.md=03330c0adc5c321f -->
<!-- sync: backend-ownership.md=9ca5c8030acd972c -->
<!-- sync: backend-rate-limit.md=5770db3d71475d11 -->
<!-- sync: backend-redis-cache.md=86ce5ccbbe5436f0 -->
<!-- sync: backend-repository-files.md=51237e1289dfa9f9 -->
<!-- sync: backend-router-params.md=ef106f43bc58c396 -->
<!-- sync: backend-router-wiring-tokens.md=2ed8513019572df5 -->
<!-- sync: backend-service-boundary-tokens.md=04e677f007379c29 -->
<!-- sync: backend-service-injection.md=84cf67e2155221a8 -->
<!-- sync: backend-sse.md=69de863a0eaf5e50 -->
<!-- sync: backend-table-design.md=2ea4f7da3b9f4bd3 -->
<!-- sync: backend-testing.md=e87015a8e84b10f9 -->
<!-- sync: backend-transaction.md=47800e8e0fc28137 -->
<!-- sync: code-layout.md=8c1eaf01a499e622 -->
<!-- sync: decks-sync.md=e003ffe7cce93087 -->
<!-- sync: duplicate-blocks.md=de698c246870bd32 -->
<!-- sync: environment.md=dcf519deec0ba399 -->
<!-- sync: frontend-api-layer.md=22c948dcde14c1c5 -->
<!-- sync: frontend-code-conventions.md=79ee56bcc1203227 -->
<!-- sync: frontend-components.md=7ee4b218f49d81b6 -->
<!-- sync: frontend-contract.md=206935238da8611e -->
<!-- sync: frontend-design.md=7a5cfb3a6d9f0b74 -->
<!-- sync: frontend-domain.md=3ee3f805d5b6eace -->
<!-- sync: frontend-i18n.md=8f29e0573d1d25b6 -->
<!-- sync: frontend-makefile.md=f524b841137120d9 -->
<!-- sync: frontend-routing.md=7a4605df9f4fb4c0 -->
<!-- sync: frontend-screens.md=0280436758edc3bc -->
<!-- sync: omp-ast-rules.md=0c012436afb7797a -->
<!-- sync: omp-conventions.md=546f0fd0e065ab7d -->
<!-- sync: omp-hook-crash-guard.md=68b9f293ce5a89af -->
<!-- sync: omp-hooks.md=995de20561dd2c4c -->
<!-- sync: omp-naming-consistency.md=23a6c62b84d1fc6d -->
<!-- sync: omp-skills.md=2c4f9e858c403742 -->
<!-- sync: root-git-workflow.md=d623ac8f064686ae -->
<!-- sync: root-makefile.md=c1babd5ac8402a12 -->
<!-- sync: tooling.md=3f0fbcc88756686c -->
<!-- sync: strict-additive-writes.ts=b6b854ab47ba3576 -->
<!-- sync: strict-backend-app-structure.ts=78a545055f47d91c -->
<!-- sync: strict-backend-migrations.ts=701d0342f53006dd -->
<!-- sync: strict-command-routing.ts=1937b2e0fd04dee2 -->
<!-- sync: strict-frontend-app-structure.ts=ff3bfbaaae973a76 -->
<!-- sync: strict-no-subagents.ts=442ea25cec44fa09 -->
<!-- sync: strict-no-vcs-publish.ts=d768e02e750c2fca -->
<!-- sync: strict-tooling.ts=0a81c93d6f73dab6 -->
<!-- sync: check-ast-rules.ts=02939fa97e028c08 -->
<!-- sync: check-backend-api-http.ts=90409c0bbd181e55 -->
<!-- sync: check-backend-api-keys.ts=354c757e938e3642 -->
<!-- sync: check-backend-app-setup.ts=84c011c766a386e2 -->
<!-- sync: check-backend-audit-log.ts=556ba3b7e59fb9a4 -->
<!-- sync: check-backend-auth.ts=33be64d56f12c2f8 -->
<!-- sync: check-backend-background-tasks.ts=ce650499e3873dae -->
<!-- sync: check-backend-batch.ts=85d46ba02f45a160 -->
<!-- sync: check-backend-contract.ts=a0462a878c8e5007 -->
<!-- sync: check-backend-core-config.ts=80bf2b91f94b74c4 -->
<!-- sync: check-backend-domain.ts=552a5afc0b045997 -->
<!-- sync: check-backend-exceptions.ts=3c31efcca50c31b1 -->
<!-- sync: check-backend-file-upload.ts=b24433ded49eb052 -->
<!-- sync: check-backend-integration-configuration.ts=4b408258d26c231e -->
<!-- sync: check-backend-integration.ts=b8ca9d81a1e1830a -->
<!-- sync: check-backend-middleware.ts=cf8567c4fcca47f3 -->
<!-- sync: check-backend-migrations.ts=08d80fb2be254758 -->
<!-- sync: check-backend-model-files.ts=db139dedd0648874 -->
<!-- sync: check-backend-naming.ts=1d90130ea78e6da8 -->
<!-- sync: check-backend-ownership.ts=fac9867cc93b8452 -->
<!-- sync: check-backend-rate-limit.ts=090e56461e91a388 -->
<!-- sync: check-backend-redis-cache.ts=e6d84753c9616e41 -->
<!-- sync: check-backend-repository-files.ts=1e0f1787cf35cc59 -->
<!-- sync: check-backend-router-params.ts=4cef66f1ed7020d9 -->
<!-- sync: check-backend-service-injection.ts=3ab6ab63323b8bf6 -->
<!-- sync: check-backend-sse.ts=f3cc51a43e2638dd -->
<!-- sync: check-backend-table-design.ts=9298a930fd8b44f9 -->
<!-- sync: check-backend-tests.ts=8b65f499134ebb57 -->
<!-- sync: check-backend-transaction.ts=6ddacba3d9722829 -->
<!-- sync: check-code-layout.ts=0a3998a4f0795907 -->
<!-- sync: check-decks-sync.ts=3aa02d4778e4b828 -->
<!-- sync: check-duplicate-blocks.ts=c9e3470b7715a4a6 -->
<!-- sync: check-environment.ts=231bbdc4b01fa901 -->
<!-- sync: check-frontend-api-layer.ts=4038458acebdf783 -->
<!-- sync: check-frontend-code.ts=1bc3d307fdaef446 -->
<!-- sync: check-frontend-components.ts=3785d33d702d0e62 -->
<!-- sync: check-frontend-contract.ts=9ba1ec63e65b0fa0 -->
<!-- sync: check-frontend-design.ts=41a654f4e8104cc5 -->
<!-- sync: check-frontend-domain.ts=fe7da6b13669af1f -->
<!-- sync: check-frontend-i18n.ts=8eb8db6d586b60e6 -->
<!-- sync: check-frontend-routing.ts=0012c29f0d99d8fe -->
<!-- sync: check-frontend-screens.ts=7ebb18d72ed808b2 -->
<!-- sync: check-frontend-types.ts=369a9d67bfe44b5e -->
<!-- sync: check-makefiles.ts=81c9dd7a35ebd3fc -->
<!-- sync: check-omp-hooks.ts=7668d2fcc18ddff0 -->
<!-- sync: check-omp-rules.ts=d37fe1e368677b95 -->
<!-- sync: check-omp-skills.ts=4a53afb496d42ca8 -->
<!-- sync: check-omp-types.ts=38ca205797d33401 -->
<!-- sync: check-tooling.ts=dec90cb9a2b57d71 -->
<!-- sync: check-verify.ts=000771942a476ef1 -->
<!-- sync: lib/ast-rules.ts=7d8313da1927a4d5 -->
<!-- sync: lib/backend-api-flow.ts=5c3aaeb6bef005a6 -->
<!-- sync: lib/backend-api-http.ts=232b35cd37c82bd4 -->
<!-- sync: lib/backend-auth.ts=6a1ea97072e8c938 -->
<!-- sync: lib/backend-domain-layers.ts=2ff2f5555721a967 -->
<!-- sync: lib/backend-domain-structure.ts=532e16c9aa32bf2b -->
<!-- sync: lib/backend-exceptions.ts=4979de50880f3ab5 -->
<!-- sync: lib/backend-external-api-probe.ts=725e9b18ba527e80 -->
<!-- sync: lib/backend-integration-configuration.ts=fb2b7e8770d8cb83 -->
<!-- sync: lib/backend-layout.ts=f6e8215318a7f1c7 -->
<!-- sync: lib/backend-migration-policy.ts=3fb285a84de60aa6 -->
<!-- sync: lib/backend-model-files.ts=850424f4ca8939b5 -->
<!-- sync: lib/backend-naming.ts=543dcd6120a18fa1 -->
<!-- sync: lib/backend-orm-sync.ts=948d6662c56f09bc -->
<!-- sync: lib/backend-reachability.ts=4824137ecc341bd4 -->
<!-- sync: lib/backend-repository-files.ts=3b8f01867ced3273 -->
<!-- sync: lib/backend-service-injection.ts=71cea573cfeb3db8 -->
<!-- sync: lib/frontend-component-split.ts=1dd21be763173f9c -->
<!-- sync: lib/frontend-contract.ts=2e807ecb7e0adea0 -->
<!-- sync: lib/frontend-i18n.ts=6d311e5592da6d1f -->
<!-- sync: lib/frontend-record-dialog.ts=a1233b5b28c3adbd -->
<!-- sync: lib/frontend-request-contract.ts=97e595a412f31ee5 -->
<!-- sync: lib/frontend-routes.ts=1987e8f42a6f2c27 -->
<!-- sync: lib/frontend-screen-probe.ts=7812dffbc3e11bb0 -->
<!-- sync: lib/frontend-source.ts=15398f35008f4fd9 -->
<!-- sync: lib/frontend-types.ts=cfe765929a1acd76 -->
<!-- sync: lib/frontend-usage.ts=62098e60e5036095 -->
<!-- sync: lib/harness-env.d.ts=c41ee1561d50960b -->
<!-- sync: lib/hook-domain-literals.ts=1cfff42c134aac12 -->
<!-- sync: lib/hook-dormancy.ts=764526765b1aba69 -->
<!-- sync: lib/hook-duplicate-blocks.ts=858b445b6777b8f8 -->
<!-- sync: lib/hook-metrics.ts=0e383f687f1c56da -->
<!-- sync: lib/hook-mutating-tools.ts=3b2a274bb4e25182 -->
<!-- sync: lib/hook-project-root.ts=952794df40797bbc -->
<!-- sync: lib/hook-rule-hint.ts=a9e6b3b9f9262179 -->
<!-- sync: lib/hook-safety-guard.ts=6d23050389a76a12 -->
<!-- sync: lib/hook-scope.ts=21a1b6fab8c467bd -->
<!-- sync: lib/hook-tool-paths.ts=d6ce01bffacf2f8a -->
<!-- sync: lib/hook-visibility.ts=378b831827345c84 -->
<!-- sync: ast-grep/rules/audit/=fa43ff9131409a46 -->
<!-- sync: ast-grep/rules/audit-readonly/=4371bf3c9670540a -->
<!-- sync: ast-grep/rules/auth/=ef53c5cd221f6c11 -->
<!-- sync: ast-grep/rules/background/=2631432e24043280 -->
<!-- sync: ast-grep/rules/batch/=83315096b3e5ef98 -->
<!-- sync: ast-grep/rules/cache/=0c4f126bc1ea5cd5 -->
<!-- sync: ast-grep/rules/conventions/=f9af2070ed6ab3d6 -->
<!-- sync: ast-grep/rules/domain/=ccec8670ed0fef6e -->
<!-- sync: ast-grep/rules/env-security/=b3302595d17d11db -->
<!-- sync: ast-grep/rules/environment/=fb6e9a8e5845def9 -->
<!-- sync: ast-grep/rules/exceptions/=16910346cf860f6d -->
<!-- sync: ast-grep/rules/factory/=f12bdc8bde61c55a -->
<!-- sync: ast-grep/rules/frontend-api/=c7b82385c1a92ade -->
<!-- sync: ast-grep/rules/frontend-screen/=1c0b4de411947650 -->
<!-- sync: ast-grep/rules/integration/=90b1990249a39920 -->
<!-- sync: ast-grep/rules/layering/=0cd53dee4be2a527 -->
<!-- sync: ast-grep/rules/logging/=e8a48abc7061fc3c -->
<!-- sync: ast-grep/rules/model/=bac1703a11ddad1d -->
<!-- sync: ast-grep/rules/naming/=20d21ed70309940d -->
<!-- sync: ast-grep/rules/offload/=4bb3cc65a9370b86 -->
<!-- sync: ast-grep/rules/ownership/=9723397c4a35ebf5 -->
<!-- sync: ast-grep/rules/ownership-router/=cf764d3af48ee904 -->
<!-- sync: ast-grep/rules/router/=59636a78715e8cef -->
<!-- sync: ast-grep/rules/service/=45cc71c05ceb3001 -->
<!-- sync: ast-grep/rules/sse/=22cb7d807c4ea3fb -->
<!-- sync: ast-grep/rules/transaction/=c613686939e1ac96 -->
<!-- sync: ast-grep/rules/upload/=db8cc2d3547eabc2 -->
<!-- sync: extensions/continuity/=40d927f1033dfc6f -->

# 우리 하네스 (OMP) 소개

개발 워크플로우의 백본 — 규칙, 훅, 스킬, 도구

<div class="muted center">이 발표는 reveal.js로 제작되었습니다</div>

---

<!-- _class: lead -->

# 하네스란?

- **개발 워크플로우의 백본** — 모든 세션에 영향을 주는 기반 시스템
- 코드 품질을 **규칙으로 강제**하고, 실수를 **훅으로 차단**
- 문서·설정·도구가 **한 곳(`.omp/`)에 모여** 일관된 컨벤션 유지
- "이렇게 하면 안 돼"를 **말로 전달**하는 대신 **자동으로 검사**

---

# 프로젝트 구조

FastAPI + React 모노레포

<div class="columns">

<div>

## Backend

- **FastAPI** + SQLAlchemy 2.0 (async)
- **Alembic** 마이그레이션
- **Pydantic 2** 스키마
- **APScheduler** 배치 작업
- Python ≥ 3.13, uv 관리

</div>

<div>

## Frontend

- **Vite** + React + TypeScript
- 컴포넌트 기반 UI
- ESLint + 타입 체크

<div class="muted" style="margin-top:1.5em">하네스는 이 두 영역의 컨벤션을 모두 관리합니다</div>

</div>

</div>

---

# 하네스의 심장: `.omp/`

```text
.omp/
├── AGENTS.md          # 프로젝트 가이드 (항상 로드)
├── RULES.md           # 고정 규칙 (Session Safety 등)
├── rules/             # 도메인 규칙 17개 (동적 로드)
├── ast-grep/          # rules/ (AST 패턴 규칙 38개) + tests/ (규칙별 실증 케이스)
├── extensions/        # 자동 로드되는 세션 확장 (continuity — 압축 복구·루프 승급·세션 상태)
├── hooks/             # pre/post 이벤트 훅
├── skills/            # 스킬 (slidev 등)
├── config.yml         # 프로젝트 설정
├── mcp.json           # MCP 서버 (context7)
└── lsp.json           # 언어 서버 (pyright, ruff, tsserver)
```

---

# 규칙 시스템 (`rules/`)

<div class="columns">

<div>

- **동적 로드** — 세션 시작 시 name + globs + description만 주입
- 내용은 `rule://<name>`으로 **필요할 때만** 읽음
- 도메인별 규칙:
  - `backend-domain`, `backend-service`
  - `backend-batch`, `backend-auth`
  - `frontend-code-conventions`
  - `omp-hooks`, `omp-ast-rules`

</div>

<div>

## AST 규칙 (`ast-grep/rules/`)

- **구조 기반 검사** — 텍스트가 아닌 AST 패턴 매칭
- 카테고리별 20개:
  - `naming/` — 변수명, 저장소 접근
  - `domain/` — 서비스 메서드, 트랜잭션
  - `router/` — 인증, 응답 모델
  - `model/` — ID 표준, 필드 패턴
  - `environment/` — 하드코딩 금지

</div>

</div>

---

# Hooks — 이벤트 인터셉터

<div class="columns">

<div>

## Pre (실행 전 차단)

- `strict-command-routing` — 명령 라우팅 강제
- `strict-backend-app-structure`
- `strict-backend-migrations`
- `strict-no-subagents`

</div>

<div>

## Post (실행 후 검사)

- `check-omp-hooks` — 훅 자체의 무결성
- `check-backend-*` — 도메인/네이밍/API/인증/배치
- `check-frontend-code`
- `check-environment` — 하드코딩 방지
- `check-verify` — 검증 강제

</div>

</div>

---

# MCP & LSP

<div class="columns">

<div>

## MCP (Model Context Protocol)

- **context7** — 라이브러리 공식 문서 조회
- 새 패턴 적용 전에 항상 최신 문서 확인
- `xd://mcp__context_query_docs`로 접근

</div>

<div>

## LSP (Language Server)

- **pyright** — Python 타입 체크
- **ruff** — 린트/포맷
- **typescript-language-server** — TS/React
- **vscode-json-language-server** — JSON 설정

</div>

</div>

---

# Skills — 역량 팩

<div class="columns">

<div>

- `<root>/skills/<name>/SKILL.md` 레이아웃
- 시스템 프롬프트에 **name + description**만 노출
- 내용은 `skill://<name>`으로 **온디맨드 로드**
- `/skill:<name>` 슬래시 명령으로 직접 호출 가능

</div>

<div>

## 현재 스킬

- **slidev** — HTML 발표 자료 제작
  - Markdown + Vue 컴포넌트
  - 코드 하이라이트, 애니메이션
  - PDF/PPTX 내보내기

<div class="muted" style="margin-top:1.5em">이 발표는 reveal.js로 제작되었습니다</div>

</div>

</div>

---

# 설정 우선순위

```text
내장 기본값  ←  전역 설정(~/.omp/agent/config.yml)
            ←  프로젝트 설정(.omp/config.yml)
            ←  CLI 오버레이(--config)
            ←  런타임 오버라이드(--model 등)
```

<div class="muted">**객체는 딥머지, 배열은 교체** — 가장 흔한 함정</div>

---

<!-- _class: lead -->

# 하네스가 주는 것

- **일관성** — 모든 세션이 같은 컨벤션
- **자동 검증** — 실수를 훅이 차단
- **문서화된 지식** — 규칙·스킬로 재사용
- **확장성** — 규칙/훅/스킬 추가만으로 확장

<div class="muted center">"말로 전달하는 컨벤션" → "코드로 강제하는 컨벤션"</div>

---

<!-- _class: lead -->

# 감사합니다

<div class="muted center">이 발표는 reveal.js로 제작되었습니다</div>
