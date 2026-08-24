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
<!-- sync: backend-api-http.md=215dc5192b1a97b4 -->
<!-- sync: backend-api-keys.md=240f10d0c15e7197 -->
<!-- sync: backend-app-forbidden-tokens.md=377fbcb4af5aab0f -->
<!-- sync: backend-app-setup.md=17d665e697444fd2 -->
<!-- sync: backend-audit-log.md=8ff51ab42272c7b2 -->
<!-- sync: backend-auth.md=02526a21c899cb02 -->
<!-- sync: backend-background-tasks.md=f44f5777655cd583 -->
<!-- sync: backend-batch.md=4b69b410bbc7867b -->
<!-- sync: backend-code-conventions.md=7f8ed81377c0e76a -->
<!-- sync: backend-core-config.md=dcd8e7bc6c1cbf9f -->
<!-- sync: backend-domain.md=fe1b20440ecd01c0 -->
<!-- sync: backend-exceptions.md=d36379949336814d -->
<!-- sync: backend-file-upload.md=417dc0174bf98a36 -->
<!-- sync: backend-identity-tokens.md=dc89bdba3680fdd8 -->
<!-- sync: backend-integration-configuration.md=efaf472c56d5113e -->
<!-- sync: backend-integration.md=3fd57fcc535b4e66 -->
<!-- sync: backend-makefile.md=26cc8434783021b3 -->
<!-- sync: backend-middleware.md=f54d26f09ba562a2 -->
<!-- sync: backend-migrations.md=9226922493976223 -->
<!-- sync: backend-naming.md=53f3931f84d3ce7d -->
<!-- sync: backend-ownership.md=17fc26d59cbcf0ca -->
<!-- sync: backend-rate-limit.md=5770db3d71475d11 -->
<!-- sync: backend-redis-cache.md=86ce5ccbbe5436f0 -->
<!-- sync: backend-router-params.md=acab7d3c10068fb3 -->
<!-- sync: backend-router-wiring-tokens.md=71f4c28d953f79df -->
<!-- sync: backend-service-boundary-tokens.md=4f04ef441d9c50a7 -->
<!-- sync: backend-sse.md=69de863a0eaf5e50 -->
<!-- sync: backend-table-design.md=4f4c1299879a5403 -->
<!-- sync: backend-testing.md=ab868a16f347a365 -->
<!-- sync: backend-transaction.md=4a614d04f599617d -->
<!-- sync: code-layout.md=8c1eaf01a499e622 -->
<!-- sync: decks-sync.md=e003ffe7cce93087 -->
<!-- sync: environment.md=b828a0f49ad196d2 -->
<!-- sync: frontend-code-conventions.md=cc68e285dd05954f -->
<!-- sync: frontend-makefile.md=3e01039ce085fdaf -->
<!-- sync: omp-ast-rules.md=c1c935f06f6ec5fe -->
<!-- sync: omp-conventions.md=049f922b266c970b -->
<!-- sync: omp-hook-crash-guard.md=3813240c3c5ba87d -->
<!-- sync: omp-hooks.md=b5da52e6f20bd825 -->
<!-- sync: omp-naming-consistency.md=23a6c62b84d1fc6d -->
<!-- sync: omp-skills.md=4a9d11a9c8538d89 -->
<!-- sync: root-git-workflow.md=a6dceb7c22eef3a9 -->
<!-- sync: root-makefile.md=d8c2569156bd7693 -->
<!-- sync: tooling.md=3f0fbcc88756686c -->
<!-- sync: strict-backend-app-structure.ts=a68e571b3fe846b3 -->
<!-- sync: strict-backend-migrations.ts=30df36cf60f42159 -->
<!-- sync: strict-command-routing.ts=c044efc651be598a -->
<!-- sync: strict-no-subagents.ts=442ea25cec44fa09 -->
<!-- sync: strict-tooling.ts=bdea910e68b74005 -->
<!-- sync: strict-verified-git.ts=66eeb22752206f71 -->
<!-- sync: check-ast-rules.ts=9c550e3fb0eca3b4 -->
<!-- sync: check-backend-api-http.ts=e7d890676f2b1738 -->
<!-- sync: check-backend-api-keys.ts=de5cf1c710b5f721 -->
<!-- sync: check-backend-app-setup.ts=9d346085b986f045 -->
<!-- sync: check-backend-audit-log.ts=f3be787b9bf3398b -->
<!-- sync: check-backend-auth.ts=0742d955df03ef12 -->
<!-- sync: check-backend-background-tasks.ts=8705287aef3769f1 -->
<!-- sync: check-backend-batch.ts=ab8860c4a7f76d4b -->
<!-- sync: check-backend-core-config.ts=2cb89fa76aa1da1a -->
<!-- sync: check-backend-domain.ts=e2183316b26ac249 -->
<!-- sync: check-backend-exceptions.ts=fa430bcec5452d81 -->
<!-- sync: check-backend-file-upload.ts=558563db2147c655 -->
<!-- sync: check-backend-integration-configuration.ts=f7cc576ccc420a41 -->
<!-- sync: check-backend-integration.ts=dc75f4faf28f2cdd -->
<!-- sync: check-backend-middleware.ts=3983e74f4afa3425 -->
<!-- sync: check-backend-migrations.ts=64420bbdd8cc0bce -->
<!-- sync: check-backend-naming.ts=d006ca1961eefb06 -->
<!-- sync: check-backend-ownership.ts=ca9de75fa4c81a8e -->
<!-- sync: check-backend-rate-limit.ts=ce826c15969b157a -->
<!-- sync: check-backend-redis-cache.ts=26a3f3dcb609001a -->
<!-- sync: check-backend-router-params.ts=429fb0d4155c172c -->
<!-- sync: check-backend-sse.ts=c73942fabef87219 -->
<!-- sync: check-backend-table-design.ts=9c69f595e0ae1eb1 -->
<!-- sync: check-backend-tests.ts=85e7b69152385f18 -->
<!-- sync: check-backend-transaction.ts=c34288ac196d5dd5 -->
<!-- sync: check-code-layout.ts=23cc163848b4dcba -->
<!-- sync: check-decks-sync.ts=8061bf22231d60f5 -->
<!-- sync: check-environment.ts=6441b3948e6b5afa -->
<!-- sync: check-frontend-code.ts=c71fc90a21fa925b -->
<!-- sync: check-makefiles.ts=19353cedd93368ee -->
<!-- sync: check-omp-hooks.ts=54b424361d4cb410 -->
<!-- sync: check-omp-rules.ts=b372038336690fc7 -->
<!-- sync: check-omp-skills.ts=c868598102614928 -->
<!-- sync: check-omp-types.ts=3171d2dbc573b359 -->
<!-- sync: check-tooling.ts=8654675f63112a1f -->
<!-- sync: check-verify.ts=ff8ef2cc05667787 -->
<!-- sync: lib/ast-rules.ts=7d8313da1927a4d5 -->
<!-- sync: lib/backend-api-flow.ts=6a4e5db31d94f1c3 -->
<!-- sync: lib/backend-api-http.ts=c69aea7655bd99b2 -->
<!-- sync: lib/backend-auth.ts=a5bca744745861b0 -->
<!-- sync: lib/backend-domain-structure.ts=db718fdf2b64f9ff -->
<!-- sync: lib/backend-exceptions.ts=ac2cfd4db338bc23 -->
<!-- sync: lib/backend-external-api-probe.ts=725e9b18ba527e80 -->
<!-- sync: lib/backend-integration-configuration.ts=4aec5cc8f8f692db -->
<!-- sync: lib/backend-migration-policy.ts=d883662d97809322 -->
<!-- sync: lib/backend-naming.ts=c1ae1ebf7e26e7c9 -->
<!-- sync: lib/backend-orm-sync.ts=43d591cd8eb0e234 -->
<!-- sync: lib/harness-env.d.ts=c41ee1561d50960b -->
<!-- sync: lib/hook-dormancy.ts=764526765b1aba69 -->
<!-- sync: lib/hook-metrics.ts=0e383f687f1c56da -->
<!-- sync: lib/hook-safety-guard.ts=a320a12fa453c3a8 -->
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
<!-- sync: ast-grep/rules/router/=fef3c4a846cbeb23 -->
<!-- sync: ast-grep/rules/service/=45cc71c05ceb3001 -->
<!-- sync: ast-grep/rules/sse/=22cb7d807c4ea3fb -->
<!-- sync: ast-grep/rules/transaction/=c613686939e1ac96 -->
<!-- sync: ast-grep/rules/upload/=db8cc2d3547eabc2 -->
<!-- sync: extensions/continuity/=3871fa0272c2f380 -->

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
