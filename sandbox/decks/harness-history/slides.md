---
marp: true
theme: einstein
paginate: true
header: "하네스 실측 & 판단 이력"
footer: "FastAPI Standard — Harness History"
style: |
  section {
    font-size: 22px;
  }
  h1 {
    font-size: 1.6em;
    margin-top: 0.1em;
    margin-bottom: 0.3em;
  }
  h2 {
    font-size: 1.25em;
  }
  table {
    font-size: 0.68em;
  }
  th, td {
    padding: 0.22em 0.5em;
  }
  .lead {
    text-align: center;
    font-size: 1.3em;
    font-weight: bold;
    margin-top: 1.2em;
  }
  .muted {
    font-size: 0.85em;
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

# 하네스 실측 & 판단 이력

<p class="lead">규칙·훅·확장이 지금의 모양이 된 이유 — 날짜 붙은 사건 기록</p>

<p class="muted">규칙 파일은 불변식만 말한다(omp-conventions: "a rule carrying every
past number stops reading as a contract"). 그 불변식을 만든 사건과 수치는
여기에 남는다. 원장 도메인의 실측은 <code>decks/ledger-measurements</code>,
이 덱은 하네스 자신의 이력이다.</p>

---

## §1 규칙·TTSR 작성 규약이 생긴 사건

| 날짜 | 사건 | 남은 규약 |
|---|---|---|
| 2026-08-31 | `condition` 을 명령 모양으로 좁히면서 `tool:write(...versions/*.py)` 스트림을 더한 편집 — 그 스트림에서 정규식이 절대 못 맞는데 모든 frontmatter 검사 통과 | 스코프 스트림마다 `fires-on` liveness 샘플 |
| 2026-08-31 | `pi.on("tool_result"` 는 발화, 직렬화형 `pi.on(\"tool_result\"` 는 무발화 — 인용부호 앞 `\\?` 로 해결 | 따옴표 포함 condition 은 JSON 이스케이프 내성 |
| 2026-08-31 | omp 가 YAML 리스트 scope 도 받는 것 확인(ttsr test 발화) — 하지만 파서·사람이 한 형태만 읽도록 문자열 한 줄로 표준화 | scope 는 문자열 한 줄 |
| 2026-09-01 | 풀스택 notice 셀: 60분 캡 타임아웃(검사 1개 남김) → 도메인 규칙을 순서+검증 구조로 바꾸자 65.5분 자체 종료 초록, 늦은-빨강 3계급 재현 0 | How-to 절은 ordered-verified 구조 |
| 2026-09-01 | `tool:edit(G)` 만 적힌 스코프는 편집 툴 구성이 바뀌는 순간 죽은 규칙 | 같은 글롭의 편집 툴 전부를 스코프에 적는다 |
| 2026-09-18 | 편집 도구 2팔 A/B(소형 TS 1개 + 이 저장소 실파일 535·310줄): 내장 `edit`(hashline) 대 외부 앵커 편집 플러그인 — 검증 12/12 동률, 결과 파일 사실상 동일, 내장 도구 오류 0 대 플러그인 1 | 편집은 내장 `edit`/`write` 만; 스코프도 그 둘만 적는다 |

---

## §2 훅 경제학 — 스코프·소유권·스로틀

| 날짜 | 실측 | 남은 규약 |
|---|---|---|
| 2026-08-29 (sandbox) | 변이 도구 결과 1회에 post 훅 36개가 write 6.8초 / bash 4.9초; 그중 3.3초는 `backend/` 편집과 무관한 하네스 메타 검사(2.7s check-omp-hooks, 0.4s check-omp-types) | 모든 post 훅은 경로 스코프 또는 `hook-scope: global — <reason>` |
| 2026-08-29 | 프롬프트 단위 프로브: 세션 벽시계의 22~36%가 도구 구간 | 비용 단위는 컨텍스트가 아니라 벽시계 |
| 2026-08-29 | 스로틀 A/B(`bench/…throttle.md`): 30초로 되돌린 셀쌍이 integration/rest 모두 TIMEOUT — 스로틀은 게이트의 지렛대가 아니다 | `FAILURE_THROTTLE_MS = 90s` 고정 |
| 2026-09-01 | post 훅 48곳이 각자 든 변이 도구 목록이 편집 툴 구성 변경에서 전부 우회됨 | `hook-mutating-tools.ts` 한 곳 소유 |
| 2026-09-01 | projectRoot 파생식 35개 복제, 순회 제외 목록 2곳 불일치 | `hook-project-root.ts` 한 곳 소유 |

---

## §3 additive-writes 가드 — 회귀와 오차단의 역사

| 날짜 | 사건 | 남은 판정 |
|---|---|---|
| 2026-08-28 | `services.py` User→Notice 통째 교체(7번째 관측), `include_router` 형제치환 회귀 1건 — 식별자 2개 규칙에 안 걸림 | 줄 모양 기반 등록-소실 판정 |
| 2026-08-28 | `+` 접두 없는 패치(`PUT 233:`)로 등록 줄 교체 — 파서 전체 무시, 회귀 1건; `CUT` 문법 부재 | 접두 선택화·삭제형 문법 추가 |
| 2026-08-28 | 훅 예외 → EISDIR 크래시 13/13, 한 셀의 edit 전멸(~10분) | 훅은 절대 던지지 않는다(fail-open) |
| 2026-08-28 | REG-WATCH 세션 상한이 앞선 파일에서 소진돼 main.py 소실 때 침묵 | 상한을 파일별로 변경 |
| 2026-08-30 | 전수 점검: 편집 2,923건 중 2,230건 `path` 없음·440건 태그 부착 — 가드 91% 무동작 | 경로 3원 판독(`path`/태그/`[rel#TAG]`) |
| 2026-08-30 | 자기 테스트 import 고치다 2회 연속 차단; 배선 줄에 이름 더하기 차단으로 라우터 등록 미완 | 테스트 경로 예외·항목 생존 기준 재정립 |

---

## §4 명령 라우팅·중복 블록

| 날짜 | 사건 | 남은 규약 |
|---|---|---|
| 2026-08-28 | ruff 자동수정이 alembic 37개 리비전을 +2256/-2413 순수 포맷 처닝 | alembic 은 포맷터 금지 |
| 2026-08-28 | `python` not found → 0.5분 우회 경로 실측 | `.venv` 절대경로 즉시 안내 |
| 2026-08-30 | eval 본문 우회 85건/25세션 (`subprocess.run(["pytest"…])`) | eval 본문도 라우팅 검사 |
| 2026-08-30 | `.py` 차단 9건 중 6건이 `backend/backend/...` 중복 경로 오타 | 오타를 먼저 짚는 안내 |
| 2026-09-01 | notice 셀: stale 전체 재작성 + 부분 편집 → 섹션 두 벌; 순번 캐스케이드가 "번호를 고쳐라"로 오도, 15분+ 재번호 루프 | `check-duplicate-blocks` 즉시 알림 (WINDOW=24, 정상 최대 반복은 마이그레이션 대칭 17줄 — 전수 스캔) |

---

## §5 continuity 확장 — 세션 규율의 실험 기록

| 날짜 | 실측 | 남은 설계 |
|---|---|---|
| 2026-08-27 | zero-base 재설계; gatefix-a2 에서 4개 시그니처 전진 중 컷 오발화; 성공 셀에서 stale red 가 END-GATE 2발 소진 | 시그니처 교체 시 시계 연장·full-gate 성공은 무조건 clear |
| 2026-08-28 | 널 블록에서 풀 게이트 무실행 종료·backend 초록 + 경고 위 종료가 finish-check ×2 통과(부검) | 하드 finish-block |
| 2026-08-29 | 하위 게이트 11회·루트 0회를 초록으로 셈 — 최종 루트 게이트 exit 2 | SUBDIR_GATE 는 풀 게이트 불인정 |
| 2026-08-29 | 인터랙티브: 프롬프트마다 상태 초기화 — p2·p3 게이트 15회 뒤 p4 가 재차단 | `.omp/state/discipline.json` 영속화 |
| 2026-08-30 | 정체 세션: ctx 96,074·턴 183초에도 성장예산 컷 무발화; rest 6셀 짝 비교에서 컷 팔 0/3, 무컷 팔 1/3 | 질병 컷 제거, 절대 상한만 env 토글 |
| 2026-09-02 | 퇴행 루프에 무제한 게이트: 차단 104회 × ~25s, 차단 프롬프트가 ctx 91k → 창 초과 종료 | `FINISH_BLOCK_MAX = 8`, 이후 빨간 종료가 곧 측정 |
| 2026-09-17 | 비례 규칙(작은 변경 = 타깃 검증 마감) 철회 — post 훅 자동 실행을 끈 뒤(`disabledExtensions`, 변이 1건당 3.8s·세션 ~570s) 전제가 사라짐 | 마감 조건은 루트 `make verify` 하나 |

---

## §6 백엔드 검사가 생긴 사건 (마이그레이션·관계)

| 날짜 | 사건 | 남은 검사 |
|---|---|---|
| 2026-09-08 | `common_standard_type_code` 가 15,806/57,457행에서 대상 없음; 원장 모델 위 relationship 14개 전수 무사용 | FK 금지·원장은 엣지의 끝점 금지 |
| 2026-09-08 | `foreign()` 을 로컬에 둔 list 엣지가 many-to-one 으로 객체 1개 반환(침묵) | `uselist=True` 요구 |
| 2026-09-09 | 손 실행 인덱스: 단일 컬럼 인덱스가 34,109 lossy blocks·1.2s/페이지 — 수정은 revision 158 (`__table_args__`) | DDL은 리비전으로만 |
| 2026-09-15 | `batch:<code>` 51~57자 vs `String(50)` — 첫 콜 로그에서 3개 잡 전사(19:04 KST) | 잡 코드 폭 비교 + 믹스인 리비전(268) |
| 2026-09-15 | `SKIPPED` 추가에 리비전 0건, 전 게이트 초록 — 첫 SKIPPED 런이 DB에 거부돼 derive 2건 영구 RUNNING | CHECK 어휘 리비전 요구 |
| 2026-09-15 | 리비전 66·70·72가 같은 파일명 — 계보 오독으로 검사 대상 2개 소실 | 시드 파일명 = 행의 정체 |
| 2026-09-16 | 리비전 248-250 `version` NOT NULL 무기본값 — 321윈도우 316,747레코드 완주 후 INSERT 사망(07:27 KST) | `compare_server_default` 상시 on |
| 2026-09-06/09-13 | 리비전 136-146 pkey 미개명 → `food_item_report_pkey1`; 게이트 전부 초록 | rename 은 pkey 동반 |

---

## §7 백엔드 검사가 생긴 사건 (원장·통합)

| 날짜 | 사건 | 남은 검사 |
|---|---|---|
| 2026-09-06 | rev 64에 시드된 2개 오퍼레이션을 5-잡 설계 내내 아무 잡도 안 읽음 — 원장은 rev 112/113 (3,393·9,633행, 2.3s·4.9s) | 페이징 오퍼레이션 ⇔ Feed 양방향 |
| 2026-09-08 | C006 전수: 569,537레코드 중 1,627 반복, 419건 원재료 상이 — 최고(最古)는 빈 껍데기 | `newest="source_updated_at"` |
| 2026-09-13 | 같은 1.09M 행: 스크린 109콜 48.5분·API 2,176콜 66분·상세 스크린 25일 | 수입식품 원장은 API로만 |
| 2026-09-14 | 라벨 패밀리: 파생 6개가 1,055,682행 원장을 각자 스캔·파싱(6회) → 패밀리 재구축으로 2스캔 1파싱 | `rebuild_<name>_family` |
| 2026-09-15 | page_size 시드 누락 11건: 바코드 피드 259,680레코드가 2,462윈도우·7.5시간(정상 247), 지연 1.1→12s, 3키 1시간 잠금 — 수정은 rev 269 | 시드는 `page_size` 명시 |
| 2026-09-15 | 스플리터 2개: `()`만 세는 쪽이 `{}` 항목을 4조각(맨숫자 746·단위 367·잔여괄호 948) | 스플리터는 `split_list` 하나 |
| 2026-09-15 | 정규화 후보 3건 측정: `(고시형)` 123,215/663,361 — 제거 시 해석률 98.41→93.84% | 정규화 규칙은 수치로 채택 |

---

## §8 프론트 검사가 생긴 사건

| 날짜 | 사건 | 남은 검사 |
|---|---|---|
| 2026-09-09 | 814 식품유형·85 상태 — 평 드롭다운 사냥; `빵` → 57,677 = SQL 카운트, 클리어로 1,640,212 복원 | facets + Autocomplete + equals |
| 2026-09-09 | rowKey 를 값으로 지음 → 충돌 키가 페이지마다 stale 행(10행 페이지에 19행) | `rowKey` 는 `.id` |
| 2026-09-09 | permanent 280px nav: 폰 콘텐츠 78px; 상태 메뉴 804px 전개 | 반응형 셸·`SELECT_MENU_MAX_HEIGHT` |
| 2026-09-09 | 기준규격 표가 174행 전부 `…` 클립 | 문장 값은 표가 아니라 아웃라인 |
| 2026-09-10 | SSE 버블 14→20→44→55자/200ms 프레임 — 토큰 착지 검증 | 스트림 검증 표준 |
| 2026-09-13 | 표시사항 탭 카드 0px vs 기준규격 16px | `SECTION_GAP` 스택 요구 |
| 2026-09-15 | 946 사건 / 1.9M 제품 — 컬럼은 99.95% 0 | 소유자 컬럼 대신 독립 리스트 |
| 2026-09-16 | "신고 0 · 사건 0" 카드(227/1,978,865); `국내 제조 식품` 124px 필요/90px 배정; 캔버스 잉크 측정(600 14px·700 12px) | `> 0` 가드·컬럼 폭 검사 |
| 2026-09-16 | 리스트 훅 재사용 룩업: 행 클릭이 직전 제품 다이얼로그(886px 남의 회사) | 룩업은 전용 훅 |

---

## §9 통합·스킬 실측

| 날짜 | 사건 | 남은 절차 |
|---|---|---|
| 2026-09-05 | `search-food-nutrition` 501+ → HTTP 200 빈 리스트(피드 끝과 동형); I2520 구간별 컬럼 충전율 함정 | 천장 이분탐색·플로어 가드 |
| 2026-09-06 | 두 포털 무로그인 측정 절차 확립; downgrade 로 1,072,054행·7시간 증발 | 원장 create 아래로 downgrade 금지 |
| 2026-09-07 | 첫 크론 밤: 2,258윈도우·3키 6h05m — 첫 실행이 윈도우 1에서 1시간 대기(정상) | 쿼터는 대기 |
| 2026-09-13 | impfood: 2콜/s 응답·3콜/s 에 호스트 전체 ~15분 차단(38콜 후); httpx 는 모바일 마크업(15,216B `mo-td`)·Chrome 은 데스크톱(12,865B `pc-td`); 폼 필드 3개 추가 시 거부 | `min_interval_ms`·UA LITERAL·폼 정확 집합 |
| 2026-09-13 | `.py` 프로브를 `app/` 옆에 저장 → dev reload 가 109윈도우 중 7에서 패스 중단 | 라이브 패스 중 `backend/` 쓰기 금지 |
