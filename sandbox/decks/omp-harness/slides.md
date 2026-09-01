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
<!-- sync: backend-api-http.md=3d39899fbd261b93 -->
<!-- sync: backend-api-keys.md=240f10d0c15e7197 -->
<!-- sync: backend-app-forbidden-tokens.md=8b80f9d9fabee937 -->
<!-- sync: backend-app-setup.md=17d665e697444fd2 -->
<!-- sync: backend-audit-log.md=8ff51ab42272c7b2 -->
<!-- sync: backend-auth.md=94bcf2878675992d -->
<!-- sync: backend-background-tasks.md=f44f5777655cd583 -->
<!-- sync: backend-batch.md=69e360f96552e3c9 -->
<!-- sync: backend-code-conventions.md=7f8ed81377c0e76a -->
<!-- sync: backend-core-config.md=2df96e9e761e6fea -->
<!-- sync: backend-domain.md=fe2388099b899e5d -->
<!-- sync: backend-exceptions.md=63e9a9e48c73778d -->
<!-- sync: backend-file-upload.md=417dc0174bf98a36 -->
<!-- sync: backend-identity-tokens.md=e3d64c5cb15a48f5 -->
<!-- sync: backend-integration-configuration.md=e8f046146137257b -->
<!-- sync: backend-integration.md=f9cd0a15ed9ea08c -->
<!-- sync: backend-makefile.md=7f10901469427649 -->
<!-- sync: backend-middleware.md=0b9ef780cf382b33 -->
<!-- sync: backend-migrations.md=3b8dfbfbc558495b -->
<!-- sync: backend-model-files.md=b2c5f76dc38e3ed2 -->
<!-- sync: backend-naming.md=48441146a1ce5cbd -->
<!-- sync: backend-ownership.md=9ca5c8030acd972c -->
<!-- sync: backend-rate-limit.md=5770db3d71475d11 -->
<!-- sync: backend-redis-cache.md=86ce5ccbbe5436f0 -->
<!-- sync: backend-repository-files.md=e621f8a3fefaa156 -->
<!-- sync: backend-router-params.md=acab7d3c10068fb3 -->
<!-- sync: backend-router-wiring-tokens.md=2c0e5f32af9a0587 -->
<!-- sync: backend-service-boundary-tokens.md=1a3a836df0cd5829 -->
<!-- sync: backend-service-injection.md=b6f17e87ebce4947 -->
<!-- sync: backend-sse.md=69de863a0eaf5e50 -->
<!-- sync: backend-table-design.md=4f4c1299879a5403 -->
<!-- sync: backend-testing.md=3af9eb79c0eb5f08 -->
<!-- sync: backend-transaction.md=4a614d04f599617d -->
<!-- sync: code-layout.md=8c1eaf01a499e622 -->
<!-- sync: decks-sync.md=e003ffe7cce93087 -->
<!-- sync: environment.md=dcf519deec0ba399 -->
<!-- sync: frontend-api-layer.md=c31bd116ed2ebd9d -->
<!-- sync: frontend-code-conventions.md=64e1590ef665f554 -->
<!-- sync: frontend-components.md=7ee4b218f49d81b6 -->
<!-- sync: frontend-contract.md=adcdb4376126cc8f -->
<!-- sync: frontend-design.md=7a5cfb3a6d9f0b74 -->
<!-- sync: frontend-domain.md=c1cb27d012094a6e -->
<!-- sync: frontend-i18n.md=2e3fe1bebc2cad91 -->
<!-- sync: frontend-makefile.md=f524b841137120d9 -->
<!-- sync: frontend-routing.md=7a4605df9f4fb4c0 -->
<!-- sync: frontend-screens.md=75deaa56a527046b -->
<!-- sync: omp-ast-rules.md=c1c935f06f6ec5fe -->
<!-- sync: omp-conventions.md=f15148f96ba61fcc -->
<!-- sync: omp-hook-crash-guard.md=a738e96b64572770 -->
<!-- sync: omp-hooks.md=50beab38a8dac824 -->
<!-- sync: omp-naming-consistency.md=23a6c62b84d1fc6d -->
<!-- sync: omp-skills.md=b7a6665acf3eb2c2 -->
<!-- sync: root-git-workflow.md=d623ac8f064686ae -->
<!-- sync: root-makefile.md=14489c052a8ebc37 -->
<!-- sync: tooling.md=3f0fbcc88756686c -->
<!-- sync: strict-additive-writes.ts=b6b854ab47ba3576 -->
<!-- sync: strict-backend-app-structure.ts=c77cfecdda8db921 -->
<!-- sync: strict-backend-migrations.ts=701d0342f53006dd -->
<!-- sync: strict-command-routing.ts=1937b2e0fd04dee2 -->
<!-- sync: strict-no-subagents.ts=a60f42f59cd92d89 -->
<!-- sync: strict-no-vcs-publish.ts=d768e02e750c2fca -->
<!-- sync: strict-tooling.ts=0a81c93d6f73dab6 -->
<!-- sync: check-ast-rules.ts=4ff5ebb7e669cdcf -->
<!-- sync: check-backend-api-http.ts=7d815cf226e74ecc -->
<!-- sync: check-backend-api-keys.ts=de367c8e35e2a93f -->
<!-- sync: check-backend-app-setup.ts=f148f00a59aa765d -->
<!-- sync: check-backend-audit-log.ts=a7cd9c7806dc9ca4 -->
<!-- sync: check-backend-auth.ts=ee564bb32028f31d -->
<!-- sync: check-backend-background-tasks.ts=9f072eb78d6c9cb6 -->
<!-- sync: check-backend-batch.ts=b15f6b399d64392e -->
<!-- sync: check-backend-core-config.ts=356032ad613d6a96 -->
<!-- sync: check-backend-domain.ts=a20df1210c168b86 -->
<!-- sync: check-backend-exceptions.ts=4ec4128348117404 -->
<!-- sync: check-backend-file-upload.ts=521ff1840bf25dc0 -->
<!-- sync: check-backend-integration-configuration.ts=9f98d6294c9ca098 -->
<!-- sync: check-backend-integration.ts=e18cd13d79573aa6 -->
<!-- sync: check-backend-middleware.ts=6211305a529ebcc9 -->
<!-- sync: check-backend-migrations.ts=b43ada85e0680807 -->
<!-- sync: check-backend-model-files.ts=c0039401fba55fa2 -->
<!-- sync: check-backend-naming.ts=6ac63ba3b8457d64 -->
<!-- sync: check-backend-ownership.ts=48fb2c0f86301d00 -->
<!-- sync: check-backend-rate-limit.ts=3cc784fd7c119665 -->
<!-- sync: check-backend-redis-cache.ts=0e8daba9e768e092 -->
<!-- sync: check-backend-repository-files.ts=908200620a828156 -->
<!-- sync: check-backend-router-params.ts=adb1d9fd2598a204 -->
<!-- sync: check-backend-service-injection.ts=5e87c8bb24e29b14 -->
<!-- sync: check-backend-sse.ts=ce52afc09d2a4f04 -->
<!-- sync: check-backend-table-design.ts=bfb89ad64e391d1d -->
<!-- sync: check-backend-tests.ts=ee649bd26d472f9c -->
<!-- sync: check-backend-transaction.ts=97019a3bb090d70e -->
<!-- sync: check-code-layout.ts=1110e6c734757dd6 -->
<!-- sync: check-decks-sync.ts=d1060909b737414c -->
<!-- sync: check-environment.ts=008228e5b3559397 -->
<!-- sync: check-frontend-api-layer.ts=ba83fd6740fa461b -->
<!-- sync: check-frontend-code.ts=6ee23f31ed996c85 -->
<!-- sync: check-frontend-components.ts=1a8f7cab531951e0 -->
<!-- sync: check-frontend-contract.ts=9dc7673ae18fd3db -->
<!-- sync: check-frontend-design.ts=6bcc974941a064a6 -->
<!-- sync: check-frontend-domain.ts=78da129a434a2fd6 -->
<!-- sync: check-frontend-i18n.ts=6442b9c59325ca28 -->
<!-- sync: check-frontend-routing.ts=128561a7bde1f3f2 -->
<!-- sync: check-frontend-screens.ts=f68354fbedf2cf5e -->
<!-- sync: check-frontend-types.ts=c6b04081395c5d84 -->
<!-- sync: check-makefiles.ts=03eec069e9e6e72f -->
<!-- sync: check-omp-hooks.ts=959d6e2fdb461e17 -->
<!-- sync: check-omp-rules.ts=6241c71eee4133e3 -->
<!-- sync: check-omp-skills.ts=67831f31a4b0b420 -->
<!-- sync: check-omp-types.ts=8171ad53424a7feb -->
<!-- sync: check-tooling.ts=10b444f2217c3588 -->
<!-- sync: check-verify.ts=5a28d5df52b21485 -->
<!-- sync: lib/ast-rules.ts=7d8313da1927a4d5 -->
<!-- sync: lib/backend-api-flow.ts=26e8483ad319865c -->
<!-- sync: lib/backend-api-http.ts=e9c8e23bb9b17cae -->
<!-- sync: lib/backend-auth.ts=a5bca744745861b0 -->
<!-- sync: lib/backend-domain-layers.ts=2ff2f5555721a967 -->
<!-- sync: lib/backend-domain-structure.ts=b5bfd745c7280afc -->
<!-- sync: lib/backend-exceptions.ts=8be50968435c4e3c -->
<!-- sync: lib/backend-external-api-probe.ts=725e9b18ba527e80 -->
<!-- sync: lib/backend-integration-configuration.ts=20b318ad6d75681e -->
<!-- sync: lib/backend-migration-policy.ts=41220d767eb69255 -->
<!-- sync: lib/backend-model-files.ts=63ba048eb740a730 -->
<!-- sync: lib/backend-naming.ts=3fd876d8e4221309 -->
<!-- sync: lib/backend-orm-sync.ts=43d591cd8eb0e234 -->
<!-- sync: lib/backend-repository-files.ts=abf6a4b480ded88b -->
<!-- sync: lib/backend-service-injection.ts=695f8b8b7ccb602f -->
<!-- sync: lib/frontend-component-split.ts=5d7c4040d53a408c -->
<!-- sync: lib/frontend-contract.ts=2c683f9dd7045c4a -->
<!-- sync: lib/frontend-i18n.ts=6d311e5592da6d1f -->
<!-- sync: lib/frontend-record-dialog.ts=36b6e3163c1afee0 -->
<!-- sync: lib/frontend-request-contract.ts=97e595a412f31ee5 -->
<!-- sync: lib/frontend-routes.ts=5ddfee9035b48275 -->
<!-- sync: lib/frontend-screen-probe.ts=7812dffbc3e11bb0 -->
<!-- sync: lib/frontend-source.ts=5fe662fafd8aab3e -->
<!-- sync: lib/frontend-types.ts=18716bd9721377f5 -->
<!-- sync: lib/frontend-usage.ts=62098e60e5036095 -->
<!-- sync: lib/harness-env.d.ts=c41ee1561d50960b -->
<!-- sync: lib/hook-domain-literals.ts=5853758bdcc845ad -->
<!-- sync: lib/hook-dormancy.ts=764526765b1aba69 -->
<!-- sync: lib/hook-metrics.ts=0e383f687f1c56da -->
<!-- sync: lib/hook-rule-hint.ts=a9e6b3b9f9262179 -->
<!-- sync: lib/hook-safety-guard.ts=6d23050389a76a12 -->
<!-- sync: lib/hook-scope.ts=21a1b6fab8c467bd -->
<!-- sync: lib/hook-tool-paths.ts=0bec0929966aab07 -->
<!-- sync: lib/hook-visibility.ts=378b831827345c84 -->
<!-- sync: ast-grep/rules/audit/=fa43ff9131409a46 -->
<!-- sync: ast-grep/rules/audit-readonly/=4371bf3c9670540a -->
<!-- sync: ast-grep/rules/auth/=ef53c5cd221f6c11 -->
<!-- sync: ast-grep/rules/background/=2631432e24043280 -->
<!-- sync: ast-grep/rules/batch/=d8b3cf5bda13247d -->
<!-- sync: ast-grep/rules/cache/=0c4f126bc1ea5cd5 -->
<!-- sync: ast-grep/rules/conventions/=f9af2070ed6ab3d6 -->
<!-- sync: ast-grep/rules/domain/=9deae1c972838f6c -->
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
<!-- sync: ast-grep/rules/router/=945a6f4bd5297fe5 -->
<!-- sync: ast-grep/rules/service/=45cc71c05ceb3001 -->
<!-- sync: ast-grep/rules/sse/=22cb7d807c4ea3fb -->
<!-- sync: ast-grep/rules/transaction/=c613686939e1ac96 -->
<!-- sync: ast-grep/rules/upload/=db8cc2d3547eabc2 -->
<!-- sync: extensions/continuity/=64c90738a383c46c -->

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
