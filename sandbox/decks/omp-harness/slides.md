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
<!-- sync: backend-api-http.md=1d4ca22c74870840 -->
<!-- sync: backend-api-keys.md=240f10d0c15e7197 -->
<!-- sync: backend-app-forbidden-tokens.md=8b80f9d9fabee937 -->
<!-- sync: backend-app-setup.md=17d665e697444fd2 -->
<!-- sync: backend-audit-log.md=8ff51ab42272c7b2 -->
<!-- sync: backend-auth.md=94bcf2878675992d -->
<!-- sync: backend-background-tasks.md=f44f5777655cd583 -->
<!-- sync: backend-batch.md=65c45b90acb2340f -->
<!-- sync: backend-code-conventions.md=7f8ed81377c0e76a -->
<!-- sync: backend-core-config.md=dcd8e7bc6c1cbf9f -->
<!-- sync: backend-domain.md=6ba32e699fcc7876 -->
<!-- sync: backend-exceptions.md=d36379949336814d -->
<!-- sync: backend-file-upload.md=417dc0174bf98a36 -->
<!-- sync: backend-identity-tokens.md=6cb5ac851893ae08 -->
<!-- sync: backend-integration-configuration.md=b0ef98683632508c -->
<!-- sync: backend-integration.md=3fd57fcc535b4e66 -->
<!-- sync: backend-makefile.md=f25f9e888286eaa6 -->
<!-- sync: backend-middleware.md=f54d26f09ba562a2 -->
<!-- sync: backend-migrations.md=4c2a4d6b7d02b93b -->
<!-- sync: backend-naming.md=a9dc70a6e7e74b0c -->
<!-- sync: backend-ownership.md=17fc26d59cbcf0ca -->
<!-- sync: backend-rate-limit.md=5770db3d71475d11 -->
<!-- sync: backend-redis-cache.md=86ce5ccbbe5436f0 -->
<!-- sync: backend-router-params.md=acab7d3c10068fb3 -->
<!-- sync: backend-router-wiring-tokens.md=2c0e5f32af9a0587 -->
<!-- sync: backend-service-boundary-tokens.md=1a3a836df0cd5829 -->
<!-- sync: backend-sse.md=69de863a0eaf5e50 -->
<!-- sync: backend-table-design.md=4f4c1299879a5403 -->
<!-- sync: backend-testing.md=1b13201da3bbfe13 -->
<!-- sync: backend-transaction.md=4a614d04f599617d -->
<!-- sync: code-layout.md=8c1eaf01a499e622 -->
<!-- sync: decks-sync.md=e003ffe7cce93087 -->
<!-- sync: environment.md=b828a0f49ad196d2 -->
<!-- sync: frontend-code-conventions.md=b372444a2ca6c4e1 -->
<!-- sync: frontend-makefile.md=3c32695481893fee -->
<!-- sync: omp-ast-rules.md=c1c935f06f6ec5fe -->
<!-- sync: omp-conventions.md=23082fc5ca93f25f -->
<!-- sync: omp-hook-crash-guard.md=a738e96b64572770 -->
<!-- sync: omp-hooks.md=b708e838eb2f83f4 -->
<!-- sync: omp-naming-consistency.md=23a6c62b84d1fc6d -->
<!-- sync: omp-skills.md=4a9d11a9c8538d89 -->
<!-- sync: root-git-workflow.md=d623ac8f064686ae -->
<!-- sync: root-makefile.md=eb585864798e1655 -->
<!-- sync: tooling.md=3f0fbcc88756686c -->
<!-- sync: strict-additive-writes.ts=b6b854ab47ba3576 -->
<!-- sync: strict-backend-app-structure.ts=8f7a405fd926c26f -->
<!-- sync: strict-backend-migrations.ts=c61439345aa57805 -->
<!-- sync: strict-command-routing.ts=db92c85fa488dda3 -->
<!-- sync: strict-no-subagents.ts=a60f42f59cd92d89 -->
<!-- sync: strict-no-vcs-publish.ts=d768e02e750c2fca -->
<!-- sync: strict-tooling.ts=d40ca3b4544135ce -->
<!-- sync: check-ast-rules.ts=4ff5ebb7e669cdcf -->
<!-- sync: check-backend-api-http.ts=7d815cf226e74ecc -->
<!-- sync: check-backend-api-keys.ts=de367c8e35e2a93f -->
<!-- sync: check-backend-app-setup.ts=f148f00a59aa765d -->
<!-- sync: check-backend-audit-log.ts=a7cd9c7806dc9ca4 -->
<!-- sync: check-backend-auth.ts=ee564bb32028f31d -->
<!-- sync: check-backend-background-tasks.ts=9f072eb78d6c9cb6 -->
<!-- sync: check-backend-batch.ts=b15f6b399d64392e -->
<!-- sync: check-backend-core-config.ts=356032ad613d6a96 -->
<!-- sync: check-backend-domain.ts=19ccd54519cabc4c -->
<!-- sync: check-backend-exceptions.ts=4ec4128348117404 -->
<!-- sync: check-backend-file-upload.ts=521ff1840bf25dc0 -->
<!-- sync: check-backend-integration-configuration.ts=9f98d6294c9ca098 -->
<!-- sync: check-backend-integration.ts=8dd61d7853ac5af9 -->
<!-- sync: check-backend-middleware.ts=977ded202191eaa4 -->
<!-- sync: check-backend-migrations.ts=b43ada85e0680807 -->
<!-- sync: check-backend-naming.ts=6ac63ba3b8457d64 -->
<!-- sync: check-backend-ownership.ts=48fb2c0f86301d00 -->
<!-- sync: check-backend-rate-limit.ts=a2371740c096045f -->
<!-- sync: check-backend-redis-cache.ts=0e8daba9e768e092 -->
<!-- sync: check-backend-router-params.ts=adb1d9fd2598a204 -->
<!-- sync: check-backend-sse.ts=17f6ff3680a5b31b -->
<!-- sync: check-backend-table-design.ts=bfb89ad64e391d1d -->
<!-- sync: check-backend-tests.ts=b1604a2072938ec3 -->
<!-- sync: check-backend-transaction.ts=07d2fdefcd194c6d -->
<!-- sync: check-code-layout.ts=fe94d9e0982daf36 -->
<!-- sync: check-decks-sync.ts=d1060909b737414c -->
<!-- sync: check-environment.ts=06cbda65a3995f6e -->
<!-- sync: check-frontend-code.ts=8d2638d68947d133 -->
<!-- sync: check-makefiles.ts=a232a657107e6577 -->
<!-- sync: check-omp-hooks.ts=9d7449f363a47750 -->
<!-- sync: check-omp-rules.ts=ae4dab8106a0dfd3 -->
<!-- sync: check-omp-skills.ts=67831f31a4b0b420 -->
<!-- sync: check-omp-types.ts=8171ad53424a7feb -->
<!-- sync: check-tooling.ts=10b444f2217c3588 -->
<!-- sync: check-verify.ts=5a28d5df52b21485 -->
<!-- sync: lib/ast-rules.ts=7d8313da1927a4d5 -->
<!-- sync: lib/backend-api-flow.ts=6a4e5db31d94f1c3 -->
<!-- sync: lib/backend-api-http.ts=83b53dad31a07bc6 -->
<!-- sync: lib/backend-auth.ts=a5bca744745861b0 -->
<!-- sync: lib/backend-domain-layers.ts=2ff2f5555721a967 -->
<!-- sync: lib/backend-domain-structure.ts=c7d46f9f802db4c5 -->
<!-- sync: lib/backend-exceptions.ts=ac2cfd4db338bc23 -->
<!-- sync: lib/backend-external-api-probe.ts=725e9b18ba527e80 -->
<!-- sync: lib/backend-integration-configuration.ts=4aec5cc8f8f692db -->
<!-- sync: lib/backend-migration-policy.ts=c13387e8c6f74063 -->
<!-- sync: lib/backend-naming.ts=c1ae1ebf7e26e7c9 -->
<!-- sync: lib/backend-orm-sync.ts=43d591cd8eb0e234 -->
<!-- sync: lib/harness-env.d.ts=c41ee1561d50960b -->
<!-- sync: lib/hook-dormancy.ts=764526765b1aba69 -->
<!-- sync: lib/hook-metrics.ts=0e383f687f1c56da -->
<!-- sync: lib/hook-rule-hint.ts=b642274590acf88c -->
<!-- sync: lib/hook-safety-guard.ts=6d23050389a76a12 -->
<!-- sync: lib/hook-scope.ts=21a1b6fab8c467bd -->
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
<!-- sync: ast-grep/rules/environment/=d6f02a1f06b0032a -->
<!-- sync: ast-grep/rules/exceptions/=16910346cf860f6d -->
<!-- sync: ast-grep/rules/factory/=f12bdc8bde61c55a -->
<!-- sync: ast-grep/rules/integration/=90b1990249a39920 -->
<!-- sync: ast-grep/rules/layering/=0cd53dee4be2a527 -->
<!-- sync: ast-grep/rules/logging/=e8a48abc7061fc3c -->
<!-- sync: ast-grep/rules/model/=d95cd8eeec07de9d -->
<!-- sync: ast-grep/rules/naming/=20d21ed70309940d -->
<!-- sync: ast-grep/rules/offload/=4bb3cc65a9370b86 -->
<!-- sync: ast-grep/rules/ownership/=9723397c4a35ebf5 -->
<!-- sync: ast-grep/rules/ownership-router/=cf764d3af48ee904 -->
<!-- sync: ast-grep/rules/router/=945a6f4bd5297fe5 -->
<!-- sync: ast-grep/rules/service/=45cc71c05ceb3001 -->
<!-- sync: ast-grep/rules/sse/=22cb7d807c4ea3fb -->
<!-- sync: ast-grep/rules/transaction/=c613686939e1ac96 -->
<!-- sync: ast-grep/rules/upload/=db8cc2d3547eabc2 -->
<!-- sync: extensions/continuity/=d9b42195ac7c4743 -->

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
