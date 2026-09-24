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
<!-- sync: backend-app-forbidden-tokens.md=8b80f9d9fabee937 -->
<!-- sync: backend-app-setup.md=17d665e697444fd2 -->
<!-- sync: backend-audit-log.md=8ff51ab42272c7b2 -->
<!-- sync: backend-auth.md=96c341a1d5492ff5 -->
<!-- sync: backend-background-tasks.md=f44f5777655cd583 -->
<!-- sync: backend-batch.md=fa8e3d25de312bf2 -->
<!-- sync: backend-code-conventions.md=0bf48fdb99b9c4f1 -->
<!-- sync: backend-contract.md=c69f238167228219 -->
<!-- sync: backend-core-config.md=2df96e9e761e6fea -->
<!-- sync: backend-domain.md=dbe6792be6b862e9 -->
<!-- sync: backend-exceptions.md=f553445ca7629751 -->
<!-- sync: backend-file-upload.md=417dc0174bf98a36 -->
<!-- sync: backend-identity-tokens.md=e3d64c5cb15a48f5 -->
<!-- sync: backend-integration-configuration.md=1e174cdfbbf19744 -->
<!-- sync: backend-integration.md=44f89e3261744814 -->
<!-- sync: backend-ledger.md=0fbf11d0f400166c -->
<!-- sync: backend-makefile.md=f4f63dfbd076506b -->
<!-- sync: backend-middleware.md=0b9ef780cf382b33 -->
<!-- sync: backend-migrations.md=1720300fdec8c2fe -->
<!-- sync: backend-model-files.md=b2c5f76dc38e3ed2 -->
<!-- sync: backend-naming.md=03330c0adc5c321f -->
<!-- sync: backend-ownership.md=9ca5c8030acd972c -->
<!-- sync: backend-rate-limit.md=5770db3d71475d11 -->
<!-- sync: backend-redis-cache.md=86ce5ccbbe5436f0 -->
<!-- sync: backend-relations.md=5222b6cba034cb29 -->
<!-- sync: backend-repository-files.md=28870f5cf797f563 -->
<!-- sync: backend-router-params.md=3bdb62c32da93dcc -->
<!-- sync: backend-router-wiring-tokens.md=3cc0419cfed317b6 -->
<!-- sync: backend-service-boundary-tokens.md=1a3a836df0cd5829 -->
<!-- sync: backend-service-injection.md=84cf67e2155221a8 -->
<!-- sync: backend-sse.md=69de863a0eaf5e50 -->
<!-- sync: backend-table-design.md=d91692922aa21be9 -->
<!-- sync: backend-testing.md=b81f18fc23611894 -->
<!-- sync: backend-transaction.md=47800e8e0fc28137 -->
<!-- sync: code-layout.md=8c1eaf01a499e622 -->
<!-- sync: decks-sync.md=e003ffe7cce93087 -->
<!-- sync: duplicate-blocks.md=8a290f55aa993b55 -->
<!-- sync: environment.md=cc0c0bb3a9af5a83 -->
<!-- sync: frontend-api-layer.md=47ea05ad8c2b8d4d -->
<!-- sync: frontend-code-conventions.md=79ee56bcc1203227 -->
<!-- sync: frontend-components.md=7ee4b218f49d81b6 -->
<!-- sync: frontend-contract.md=1cebb97c2511d388 -->
<!-- sync: frontend-design.md=4f5bf4b7ebca907e -->
<!-- sync: frontend-domain.md=da92c539eca616ed -->
<!-- sync: frontend-i18n.md=8f29e0573d1d25b6 -->
<!-- sync: frontend-makefile.md=f524b841137120d9 -->
<!-- sync: frontend-routing.md=7a4605df9f4fb4c0 -->
<!-- sync: frontend-screens.md=94e26d6c46f34e22 -->
<!-- sync: omp-ast-rules.md=0c012436afb7797a -->
<!-- sync: omp-conventions.md=aeb17a00b82c1ee4 -->
<!-- sync: omp-hook-crash-guard.md=a738e96b64572770 -->
<!-- sync: omp-hooks.md=d7acae5f73299fa8 -->
<!-- sync: omp-naming-consistency.md=0517ece90d59ff30 -->
<!-- sync: omp-skills.md=56f2c3fa305af5c7 -->
<!-- sync: product-areas.md=e6eb731c0bf54c22 -->
<!-- sync: root-git-workflow.md=f0426b4545558ce8 -->
<!-- sync: root-makefile.md=288b1f949e93aea8 -->
<!-- sync: tooling.md=00ce26b50ca28f75 -->
<!-- sync: strict-additive-writes.ts=0e318ce25f5fb130 -->
<!-- sync: strict-backend-app-structure.ts=78a545055f47d91c -->
<!-- sync: strict-backend-migrations.ts=6802e1e07834ea19 -->
<!-- sync: strict-command-routing.ts=57662e7973207b0a -->
<!-- sync: strict-frontend-app-structure.ts=ff3bfbaaae973a76 -->
<!-- sync: strict-no-subagents.ts=442ea25cec44fa09 -->
<!-- sync: strict-no-vcs-publish.ts=7de84b0e1ac4d6fa -->
<!-- sync: strict-tooling.ts=d9beaa05c7b33a51 -->
<!-- sync: check-ast-rules.ts=02939fa97e028c08 -->
<!-- sync: check-backend-api-http.ts=81e8838988ca3c17 -->
<!-- sync: check-backend-api-keys.ts=354c757e938e3642 -->
<!-- sync: check-backend-app-setup.ts=84c011c766a386e2 -->
<!-- sync: check-backend-audit-log.ts=556ba3b7e59fb9a4 -->
<!-- sync: check-backend-auth.ts=33be64d56f12c2f8 -->
<!-- sync: check-backend-background-tasks.ts=ce650499e3873dae -->
<!-- sync: check-backend-batch.ts=12b6c0b152683cfc -->
<!-- sync: check-backend-contract.ts=a0462a878c8e5007 -->
<!-- sync: check-backend-core-config.ts=80bf2b91f94b74c4 -->
<!-- sync: check-backend-domain.ts=8b1ad47629cb3c90 -->
<!-- sync: check-backend-exceptions.ts=3c31efcca50c31b1 -->
<!-- sync: check-backend-file-upload.ts=b24433ded49eb052 -->
<!-- sync: check-backend-integration-configuration.ts=4b408258d26c231e -->
<!-- sync: check-backend-integration.ts=b8ca9d81a1e1830a -->
<!-- sync: check-backend-ledger.ts=5f087d56f6ac99b0 -->
<!-- sync: check-backend-middleware.ts=cf8567c4fcca47f3 -->
<!-- sync: check-backend-migrations.ts=08d80fb2be254758 -->
<!-- sync: check-backend-model-files.ts=db139dedd0648874 -->
<!-- sync: check-backend-naming.ts=1d90130ea78e6da8 -->
<!-- sync: check-backend-ownership.ts=fac9867cc93b8452 -->
<!-- sync: check-backend-rate-limit.ts=090e56461e91a388 -->
<!-- sync: check-backend-redis-cache.ts=e6d84753c9616e41 -->
<!-- sync: check-backend-relations.ts=5839cc44e1cd71cb -->
<!-- sync: check-backend-repository-files.ts=1e0f1787cf35cc59 -->
<!-- sync: check-backend-router-params.ts=5953f150de13780d -->
<!-- sync: check-backend-service-injection.ts=3ab6ab63323b8bf6 -->
<!-- sync: check-backend-sse.ts=f3cc51a43e2638dd -->
<!-- sync: check-backend-table-design.ts=17ab15c178be28e7 -->
<!-- sync: check-backend-tests.ts=9bc538e7c210e680 -->
<!-- sync: check-backend-transaction.ts=6ddacba3d9722829 -->
<!-- sync: check-code-layout.ts=9de763bb10f5a558 -->
<!-- sync: check-decks-sync.ts=3aa02d4778e4b828 -->
<!-- sync: check-duplicate-blocks.ts=4c03b54946771f2b -->
<!-- sync: check-environment.ts=574c8405173e84cd -->
<!-- sync: check-frontend-api-layer.ts=4038458acebdf783 -->
<!-- sync: check-frontend-code.ts=1bc3d307fdaef446 -->
<!-- sync: check-frontend-components.ts=3785d33d702d0e62 -->
<!-- sync: check-frontend-contract.ts=18773fbccf249d57 -->
<!-- sync: check-frontend-design.ts=7972bf12bf2a32d7 -->
<!-- sync: check-frontend-domain.ts=8cc4e64303de315c -->
<!-- sync: check-frontend-i18n.ts=8eb8db6d586b60e6 -->
<!-- sync: check-frontend-routing.ts=0012c29f0d99d8fe -->
<!-- sync: check-frontend-screens.ts=bb669c18d6be3275 -->
<!-- sync: check-frontend-types.ts=9b5dc67623a0882f -->
<!-- sync: check-makefiles.ts=bdbaa144083c13a0 -->
<!-- sync: check-omp-hooks.ts=1db35cba05aaa853 -->
<!-- sync: check-omp-rules.ts=d59c8839abde8338 -->
<!-- sync: check-omp-skills.ts=86069fd4693d7065 -->
<!-- sync: check-omp-types.ts=38ca205797d33401 -->
<!-- sync: check-product-areas.ts=3bbfe5c888d82dde -->
<!-- sync: check-tooling.ts=457b639e2a8b54c7 -->
<!-- sync: check-verify.ts=b8bc201e3f6eb167 -->
<!-- sync: lib/ast-rules.ts=7d8313da1927a4d5 -->
<!-- sync: lib/backend-api-flow.ts=e0403082dd6ac77c -->
<!-- sync: lib/backend-api-http.ts=683c0ef3f0218636 -->
<!-- sync: lib/backend-auth.ts=6a1ea97072e8c938 -->
<!-- sync: lib/backend-closed-vocab.ts=d51f7d4da416232b -->
<!-- sync: lib/backend-derivations.ts=60d21f928ddf965f -->
<!-- sync: lib/backend-domain-layers.ts=c966d9426fed0a28 -->
<!-- sync: lib/backend-domain-structure.ts=33098bb8a30462b3 -->
<!-- sync: lib/backend-exceptions.ts=4979de50880f3ab5 -->
<!-- sync: lib/backend-external-api-probe.ts=455eec117779f7ea -->
<!-- sync: lib/backend-integration-configuration.ts=b03543e09a593a99 -->
<!-- sync: lib/backend-layout.ts=5add5efa5062a197 -->
<!-- sync: lib/backend-ledger-feeds.ts=52039b0754419b1b -->
<!-- sync: lib/backend-migration-policy.ts=1815465857ab0774 -->
<!-- sync: lib/backend-model-files.ts=850424f4ca8939b5 -->
<!-- sync: lib/backend-naming.ts=543dcd6120a18fa1 -->
<!-- sync: lib/backend-orm-sync.ts=948d6662c56f09bc -->
<!-- sync: lib/backend-reachability.ts=4824137ecc341bd4 -->
<!-- sync: lib/backend-relations.ts=ebf2e04e089ecd5c -->
<!-- sync: lib/backend-repository-files.ts=3b8f01867ced3273 -->
<!-- sync: lib/backend-service-injection.ts=71cea573cfeb3db8 -->
<!-- sync: lib/frontend-component-split.ts=1dd21be763173f9c -->
<!-- sync: lib/frontend-contract.ts=03387111242d2452 -->
<!-- sync: lib/frontend-grid-width.ts=a873bc74d50b12b1 -->
<!-- sync: lib/frontend-i18n.ts=6d311e5592da6d1f -->
<!-- sync: lib/frontend-record-dialog.ts=bc487b108a11b247 -->
<!-- sync: lib/frontend-request-contract.ts=2686edaea1005aa5 -->
<!-- sync: lib/frontend-routes.ts=f0adf8485fc4777d -->
<!-- sync: lib/frontend-screen-probe.ts=7812dffbc3e11bb0 -->
<!-- sync: lib/frontend-source.ts=15398f35008f4fd9 -->
<!-- sync: lib/frontend-types.ts=56f8a667b6297239 -->
<!-- sync: lib/frontend-usage.ts=62098e60e5036095 -->
<!-- sync: lib/harness-env.d.ts=c41ee1561d50960b -->
<!-- sync: lib/hook-domain-literals.ts=1cfff42c134aac12 -->
<!-- sync: lib/hook-dormancy.ts=764526765b1aba69 -->
<!-- sync: lib/hook-duplicate-blocks.ts=eab1b04c61889f7c -->
<!-- sync: lib/hook-metrics.ts=0e383f687f1c56da -->
<!-- sync: lib/hook-mutating-tools.ts=55386356bae189c9 -->
<!-- sync: lib/hook-postgres.ts=3828add20fb653ac -->
<!-- sync: lib/hook-product-areas.ts=81c0b22f8e7a283d -->
<!-- sync: lib/hook-project-root.ts=e0d5f496cfa8b5be -->
<!-- sync: lib/hook-rule-hint.ts=a9e6b3b9f9262179 -->
<!-- sync: lib/hook-safety-guard.ts=6d23050389a76a12 -->
<!-- sync: lib/hook-scope.ts=7bdf79caa1d5a523 -->
<!-- sync: lib/hook-tool-paths.ts=09a48e5003bcd92d -->
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
<!-- sync: ast-grep/rules/model/=3096d5b4eb5b20a8 -->
<!-- sync: ast-grep/rules/naming/=20d21ed70309940d -->
<!-- sync: ast-grep/rules/offload/=4bb3cc65a9370b86 -->
<!-- sync: ast-grep/rules/ownership/=9723397c4a35ebf5 -->
<!-- sync: ast-grep/rules/ownership-router/=cf764d3af48ee904 -->
<!-- sync: ast-grep/rules/router/=8090e6b2d97520f9 -->
<!-- sync: ast-grep/rules/service/=45cc71c05ceb3001 -->
<!-- sync: ast-grep/rules/sse/=22cb7d807c4ea3fb -->
<!-- sync: ast-grep/rules/transaction/=c613686939e1ac96 -->
<!-- sync: ast-grep/rules/upload/=db8cc2d3547eabc2 -->
<!-- sync: extensions/continuity/=b31fe7b69488f60f -->

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
