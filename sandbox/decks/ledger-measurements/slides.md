---
marp: true
theme: einstein
paginate: true
header: "원장 실측 & 설계 판단 이력"
footer: "FastAPI Standard — Ledger Measurements"
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
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5em;
  }
  .columns ul {
    margin-top: 0.3em;
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
  .center {
    text-align: center;
  }
  .small {
    font-size: 0.75em;
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

# 원장 실측 & 설계 판단 이력

규칙에는 현재 계약과 한 줄 근거만 — 숫자와 경위는 여기 쌓는다

<div class="muted center">모든 수치는 실측이며 측정일을 함께 적는다</div>

---

# 1. 두 포털의 성질 (실측)

| 사실 | 식품안전나라 (openapi.foodsafetykorea.go.kr) | data.go.kr |
|---|---|---|
| 창 상한 | **1,000행** (`ERROR-336`), 5,000 요청은 거부 | 서비스별 **500 / 100** |
| 끝 판정 | 짧은 페이지, 또는 `INFO-200` | 짧은 페이지만 (빈 응답 코드 없음) |
| 쿼터 | 키 × 서비스 단위로 **시간당 약 200콜(`INFO-320`) · 하루 500콜(`INFO-300`)** — 상한과 실측은 §11 | 관측된 거부 없음 |
| 지연 | **오프셋 선형** — OFFSET 스캔 비용이 그대로 보인다 | 동일 경향 |
| 필터 | **경로 세그먼트만** 동작 (`/I0300/json/1/5/EVL_YR=2024`), 쿼리스트링은 무시 | — |
| 증분 | `LAST_UPDT_DTM` 최대 7일 (`ERROR-303`), 그 이상 거부 | — |

**연도 세그먼트는 완전 분할**: I0300 연도별 합 = 7,927,213 = 전체 total, I1420 3,397,141, I0310 316,747 (2026-09-15).
따라서 연도는 "필터"가 아니라 **피드를 쪼개는 좌표**로 쓸 수 있다.

---

# 2. 피드별 창당 지연 (mfds 한 밤, 2026-09-15)

| 피드 | 창 수 | 초/창 | | 피드 | 창 수 | 초/창 |
|---|---|---|---|---|---|---|
| `search-common-standard` | 729 | **10.4** | | `search-barcode-item-info` | 54 | 2.3 |
| `search-barcode-product-info` | 260 | 4.3 | | `search-food-recall` | 3 | 0.5 |
| `search-livestock-item-report-raw-material` | 650 | 3.4 | | `search-food-inspection-failure` | 3 | 0.4 |
| `search-individual-standard` | 400 | 3.1 | | `search-common-standard-type/-exclusion` | 6 / 6 | 0.3 |
| `search-food-raw-material` | 132 | 2.4 | | `search-product-classification` | 331 | 0.2 |
| | | | | `search-test-item` | 118 | 0.2 |

- 같은 호스트·같은 키 풀에서 **50배** 차이 — 창 수만으로 비용을 말할 수 없다.
- `search-common-standard` 혼자 2시간 06분. mfds 잡 전체는 **약 3.5시간** (2,739창).
- 야간 창은 00:00–10:00 (파생 10:00), 즉 **여유 약 6.5시간**.

---

# 3. 생산실적 3종 총 소요 모델 (2026-09-15)

| 서비스 | 행 수 | 창당 지연 (1k / 1M / 최종) | 기울기 | 한 줄 walk | 연도 분할 |
|---|---|---|---|---|---|
| I0300 식품 생산실적 | 7,927,213 | 0.19s / 3.1s / **21.6s** | 2.74 ms/1k행 | **24.9 h** | **5.7 h** |
| I1420 축산물 생산실적 | 3,397,141 | 0.38s / 16.6s / **51.2s** | 14.95 ms/1k행 | **25.0 h** | **8.5 h** |
| I0310 건기식 생산실적 | 316,747 | 2.2s / — / 4.1s | 5.5 ms/1k행 | 0.31 h | 0.11 h |
| **합** | 11,641,101 | | | **50.2 h** | **14.3 h** |

측정점 최소자승 선형모델 `ms(offset) = a + b·offset` 을 창마다 적분한 값.

- 연 1회 갱신 피드다. 연도별 행수: I0300 2016년 591,448 → 2025년 1,035,192 (10개 연도).
- **14.3 h > 6.5 h 여유** — 매일 전량 walk 는 어떤 배치 모양으로도 야간 창에 들어가지 않는다.

---

# 4. 배치 설계 판단 이력 (2026-09-15)

<div class="columns">
<div>

**만들어 본 것 — 잡 하나 = 원장 하나**
- 25개 잡·25개 cron·25개 run 으로 분해
- provider 단위 직렬화를 스케줄러 락으로 구현
- **직렬화 실측**: mfds 3잡 + data-go-kr 1잡을 동시에 run → mfds 콜은 19:40:48.387 → 48.912 → 49.169 로 겹침 0, data-go-kr 74콜은 같은 시각 병렬
- 게이트 초록 (519 tests, coverage 100%)

</div>
<div>

**폐기한 이유**
- 생산실적은 **연 1회 갱신**. 매일 걷지 않는 피드를 위해 잡·cron·run 을 25배로 늘리는 값이 비싸다
- provider 잡의 실제 병목(작은 피드가 큰 피드 뒤에서 1시간 대기)은 **걷는 양을 줄이면** 사라진다

**한 번 폐기했다가 다시 채택 (2026-09-15 저녁)**
- 09~19시 제한을 실측하고 나서: 밤은 14h, mfds 피드 총량은 18h → **어떤 순서로도 한 밤에 안 들어간다**
- 잡을 나누면 밤을 나눌 수 있다: 금 19:00 기존 피드 + 건기식 생산실적, 토 19:00 I0300(5.7h), 일 19:00 I1420(8.5h)
- provider 직렬은 스케줄러 락 하나로 유지, 키 임대는 여전히 만들지 않음

**연도 감시(total_count 비교)는 채택하지 않음**
- 연도별 `total_count` 1콜씩 (3서비스 × 10연도 = **30콜/일**, 1~2분)
- 원장의 해당 연도 행수와 다르면 그 연도만 walk
- 행수 불변 갱신을 놓치므로 **월 1회 최신 연도 강제 walk**

</div>
</div>

---

# 5. 수입식품 라벨: 화면 크롤 → API 전환 (2026-09-14)

| 경로 | 측정 | 결과 |
|---|---|---|
| 식품안전나라 화면 크롤 | 48분 / 25일치 | 전량에 수개월 |
| data.go.kr `search-import-food-label` (B553748) | 2,176창 × 500행 = **66분** | 1,087,781행 |

- 두 경로의 **연도별 건수 일치** 확인 후 화면 경로 폐기.
- 창 폭이 곧 시간: 같은 피드를 100행 창으로 걸으면 13시간, 500행 창이면 66분 — 폭은 서비스별 `integration_operation.page_size` 로 측정해 둔다.

---

# 6. 표시사항 파서 실측 (2026-09-14)

| 항목 | 값 |
|---|---|
| 읽은 라벨 | 1,044,332 / 1,055,682 선언 (98.9%) |
| heading 토큰 | **59,270종**, 3,000회 이상 등장하는 형태 289종 |
| 줄바꿈으로 잘린 목록 | 61,472건 — 섹션 끝 규칙을 "다음 측정된 heading 까지" 로 바꿔 흡수 |
| 원재료 행 (수입) | 603,692 → **771,864**, 해석률 546,569 (83.6%) → **639,612 (82.9%)** |
| 사전 이명(alias) | 43,612행 중 15,952행이 실제 사전 항목과 연결 |
| 결과 | 라벨 1,044,179 → 289,938 (제품당 1건), 알레르기 816,436 → 204,640 |

<div class="muted">파서의 상수(heading 목록·NAME_LIMIT·섹션 종료 규칙)는 전부 이 빈도표에서 나왔다 — 규칙에는 "빈도표에서 만든다" 한 줄만 둔다.</div>

---

# 7. 피드 병렬 실측 (2026-09-15)

| 시도 | 호출 | 성공 | INFO-500 | makespan |
|---|---|---|---|---|
| 식품안전나라 1피드 (직렬) | 5 | 5 | 0 | 5.6 s |
| 식품안전나라 2피드 동시(같은 키) | 10 | 7 | **3** | 11.2 s |
| 식품안전나라 3피드 동시(같은 키) | 15 | 8 | **7** | 11.9 s |
| 식품안전나라 4피드 동시(같은 키) | 20 | 8 | **12** | 14.4 s |
| 식품안전나라 3피드 = 키 3개 각각 | 15 | **15** | 0 | 13.9 s (직렬 환산 ~34 s) |
| data.go.kr 3피드 동시 | 9 | 9 | 0 | 1.3 s |
| data.go.kr 4피드 동시 | 16 | 16 | 0 | 1.8 s |
| data.go.kr 6피드 동시 | 24 | 24 | 0 | 21.3 s (가장 큰 피드가 결정) |

- **제약의 단위는 호스트가 아니라 키다**: 같은 키로 동시에 두 번 부르면 `INFO-500`, 키마다 하나씩이면 전부 성공.
- 로컬 자원은 병목이 아니다: uvicorn RSS 34 MB 고정, DB 커넥션 13개 고정(풀 여유), CPU 미미.
- **결론: 병렬은 채택하지 않았다.** 식품안전나라는 키당 동시 1콜이라 병렬하려면 키 임대(in-flight 락) 기계가 필요하고, data.go.kr만 병렬로 바꿔 얻는 시간은 금요일 20:00 주간 창(≈20 h) 안에서 의미가 없다 — 잡은 피드를 하나씩 걷는다.

---

# 8. 식품안전나라는 낮에 닫는다 (2026-09-15)

```
ERROR-503  09시~19시에는 서비스가 제한됩니다. 이용에 참고바랍니다.
```

| 사실 | 값 |
|---|---|
| 서비스 가능 시간 | **19:00 ~ 익일 09:00 KST — 밤 14시간** |
| 실측 사고 | 06:57 시작한 run이 **09:00:16** 공통기준규격 520창째에서 503 |
| 파급 | 남은 9개 피드가 2초 안에 전부 같은 503으로 실패(키 3개 모두, 0초) |
| 같은 시각 data.go.kr | 영향 없음 — 11피드 3,561창 **1h52m SUCCEEDED** |

- **읽는 법이 설계다**: 503을 일반 거절로 읽으면 초당 한 피드씩 죽고, 쿼터로 읽으면 '대기 후 같은 창부터'가 된다. `quota_codes`에 `ERROR-503: 36000`(10시간 = 09~19시)을 넣어 mfds 17개 operation 전부에 적용 — 시각 계산 코드는 두지 않는다.
- 주간 run 타임라인: 금 20:00 시작 → 금 밤 13h → 토 09~19시 대기 → 토 밤 이어 걷기 → 일 10:00 파생.


---

# 9. CHECK 본문은 alembic이 보지 않는다 (2026-09-15)

파생 잡을 SKIPPED로 세우려고 `SKIPPED`를 모델·스키마 `Literal`·TS union 세 곳에 넣었다. 리비전은 안 썼다.

| 사실 | 값 |
|---|---|
| 게이트 | `make verify` **초록** (alembic check 포함) |
| 실제 DB | `ck_batch_run_status` 는 여전히 5개 값만 허용 |
| 라이브 결과 | 첫 SKIPPED 마감이 CheckViolation → 마감 실패 → run 2개가 RUNNING 고착 |
| 2차 피해 | 고착된 derive run을 다음 fire가 '파생이 이미 돌고 있다'로 읽음 |

- **원인**: autogenerate는 제약의 존재만 비교하고 CHECK 본문(IN 목록)은 비교하지 않는다 — 세 곳을 고쳐도 네 번째(DB)는 그대로.
- **대책 3중**: (1) `check-backend-domain` → 모델 `CheckConstraint` ↔ `pg_constraint` 라이브 대조(도달 불가 시 `DORMANT` 표시, 통과 위장 안 함), (2) `check-backend-migrations` → upstream 모델과 IN 집합이 다른데 그 제약을 이름으로 다루는 미푸시 리비전이 없으면 실패, (3) 기존 `checkClosedVocabularyExposed` → 제약 ↔ 스키마 `Literal`.
- **검증**: 리비전 261을 내리면 (1)이 빨간색, 리비전 파일을 치우면 (2)가 빨간색, `Literal`에서 SKIPPED를 빼면 (3)이 빨간색.
- **부산물**: psql 경로가 두 곳이 되자 `check-tooling`이 거부 → `lib/hook-postgres.ts` 하나로 합병.

---

# 10. 창 너비가 기본값으로 퇴행했다 (2026-09-15)

`integration_operation.page_size` 는 `server_default 100`. 너비를 잡에서
operation 으로 옮길 때 11개 mfds operation 이 명시 seed 없이 기본값으로 내려갔다.

| 사실 | 값 |
|---|---|
| 바코드 피드 | 259,680행 |
| 100행 창 | **2,462창 · 7.5h** (창당 1.1s → 12s, 오프셋 증가) |
| 1000행 창 | **247창** (포털 상한 1000, 초과 시 `INFO-320`) |
| 부작용 | 호출 10배 → 쿼터 거부 15건, 키 3개 1시간 잠김 |

**provider별 현재 너비 (리비전 269 적용 후)**

| provider | 1000 | 500 | 100 |
|---|---|---|---|
| mfds-food-safety-korea | 17 (전부) | - | - |
| data-go-kr | - | 영양성분·수입라벨 2 | 푸드QR 8 · HACCP 1 |

- 이미 1000으로 **명시 seed** 되어 있던 6개(회수·부적합·건기식 품목/생산실적·식품/축산 생산실적)는 퇴행하지 않았다 — 기본값 의존이 원인이지 실수 하나가 아니다.
- 규칙: 리비전 270부터 operation seed 는 `page_size` 를 반드시 적는다(`check-backend-integration-configuration`).
- **어제 측정한 지연표(공통기준규격 10.4s/창 등)는 전부 100행 기준** — 1000행 재측정 전까지 비관적으로 읽어야 한다.

---

# 11. 쿼터는 두 층이다 — 시간당과 하루 (2026-09-16 ~ 09-17)

포털은 거절 코드 두 개로 서로 다른 한도를 말한다. 하나는 기다리면 풀리고, 하나는 그 날이 끝나야 풀린다.

| 코드 | 메시지 | 실측 임계 | 회복 |
|---|---|---|---|
| `INFO-320` | "CHNG_DT 파라미터를 사용하지 않으면 1시간당 100회까지만 호출할 수 있습니다" | **롤링 60분 키당 약 200콜** (거부 73건 범위 163~212, 평균 193) | 정확히 59분 뒤 재개 (01:14 잠김 → 02:13 재개) |
| `INFO-300` | "유효 호출건수를 이미 초과하셨습니다" | **하루 키당 정확히 500콜** (`search-livestock-production` 501/501/501번째에서 3키 동시) | 자정 |

- **단위는 키 × 서비스**다. 같은 키가 같은 날 품목 원재료 357콜을 쓴 것은 축산 생산실적의 500에 섞이지 않았다.
- **시간당 상한은 서비스마다 같지 않다**: I1420 축산 생산실적은 59분에 키당 278콜, I0310 건기식은 234콜을 넣고도 `INFO-320` 0건. 200은 상수가 아니라 계획용 하한이다.
- 포털은 시간대 검사보다 쿼터 검사를 먼저 한다 — 09:35 재시도가 `ERROR-503`이 아니라 `INFO-300`을 받았다.

**그래서 천장은 서비스당 하루 1,500창** (키 3개 × 500). 한 밤 전량 walk는 1,500창 이하 피드에서만 성립한다.

| 피드 | 창 수 | 하루 천장 대비 |
|---|---|---|
| 품목제조보고 I1250 | 1,075 | 통과 (2026-09-16 21:17→23:53) |
| 품목 원재료 | 1,075 | 통과 (2026-09-17 00:37→03:40) |
| 축산 생산실적 I1420 | 3,398 | **3일치** — 09-17 08:35 1,488창에서 `INFO-300` |
| 식품 생산실적 I0300 | 7,928 | **6일치** |

---

# 12. 한 밤 run의 시간은 walk가 아니다 (2026-09-17)

같은 밤 두 피드, 둘 다 1,075창 · 실패 0 · 1,074,179행. 걸린 시간은 30분 차이다.

| 구간 | 품목제조보고 | 품목 원재료 |
|---|---|---|
| 총 | 2h35m38s | 3h03m36s |
| 순수 walk | 1h36m25s (62%) | 2h03m54s (67%) |
| 쿼터 대기 | 58m (37%, `INFO-320` 1회) | 59m (32%, `INFO-320` 1회) |
| 원장 교체 | 13s | 약 1m |

- **대기는 한 번, 59분 고정**이다 — 롤링 60분 창이 비는 시각이지 백오프가 아니다.
- **walk 자체가 감속한다**: 품목 원재료는 첫 37분 565창(15.3창/분) → 마지막 구간 5.4창/분. 오프셋 선형 비용(§1)이 한 run 안에서 보인다.
- 그래서 창 수로 세운 예상은 앞부분만 맞는다 — 1,073창을 1.8h로 잡았고 실제는 3.06h.

**측정 방법**: `batch_step.duration_ms` 합 = walk, run 총시간 − walk − 교체 = 대기. 스텝이 창마다 남으므로 두 값은 사후에 분리된다(rule://backend-batch).

---

# 13. 오프셋은 제곱이다 — 좌표는 그걸 자른다 (2026-09-17)

2025년 한 해(I0300, 1,034,296행)를 통째로 걷고 창당 지연을 오프셋 구간별로 나눠 본 값이다.

| 오프셋 구간 | 창 수 | 창당 |
|---|---|---|
| 0 ~ 200k | 244 | **0.92s** |
| 200k ~ 400k | 200 | 1.92s |
| 400k ~ 600k | 200 | 3.30s |
| 600k ~ 800k | 200 | 4.32s |
| 800k ~ 1.0M | 200 | 5.76s |
| 1.0M ~ | 36 | **6.36s** |

완전한 직선, 기울기 **5.3ms / 1,000행**. 포털이 OFFSET 을 매번 스캔하므로 한 walk 의 총비용은 창 수의 **제곱**이다.

| 방식 | 같은 7,927,213행 | 총 walk |
|---|---|---|
| 한 줄로 | 7,928창 | 약 **48h** |
| 연도 10개로 | 각 793창 | 약 **6h** |

- 같은 창 수·같은 행·같은 키다. 8배 차이는 오직 **연도마다 오프셋을 0으로 되돌리는 것**에서 나온다.
- 그래서 좌표는 "필터"도 "기호"도 아니다 — **큰 피드를 걸을 수 있게 만드는 유일한 수단**이다.

**그래서 좌표는 설정으로 내려갔다** (리비전 271·272)

| 이전 | 이후 |
|---|---|
| `ledger_feed.FIRST_SEGMENT_YEAR = 2016` — 28개 잡이 공유하는 몸통에 3개 서비스의 사실 | `integration_operation.segment_values` — 값을 **나열**한다 |
| `range(2016, 올해+2)` — 코드가 "좌표는 연도"를 안다 | walk 는 좌표가 무엇인지 모른다 — 나열된 값을 하나씩 탐침할 뿐 |
| `Feed(..., "report_year")` — 25개 잡이 `None` 으로 넘기던 4번째 요소 | `integration_operation.segment_key` |
| 잡이 좌표를 안다 | walk 가 operation 행에 묻는다 (`segmentation_of`) |

- 넓이(`page_size`, §10)·쿼터(`quota_codes`, §11)가 간 자리로 세 번째 사실이 간 것이다.
- **빠지면 터지지 않고 느려진다** — 그래서 `check-backend-ledger` 가 세 가지를 거부한다: 잡 모듈의 **여섯 번째 상수**(허용된 다섯 이름 외에는 없다), 4요소 `Feed(...)`, 그리고 `app/batch/`·`app/services/batch/` 코드의 연도 리터럴(독스트링은 예외).
- 반증 2회: `FIRST_SEGMENT_YEAR = 2016` 한 줄 → 빨간색, `REGION_CODES = ("11", "26")` 한 줄 → 빨간색. 두 번째가 **일반화가 섬다는 증거**다 — 연도가 아니어도 잡으로 돌아오는 포털 사실은 같은 검사에 걸린다.

---

# 14. 걸을 수 없는 피드, 그리고 파일 문 (2026-09-19)

수거검사 결과(I0460)는 **2,046,504행 = 2,047창**이다. 잡 본체로 걸어 본 값:

| 시각(UTC) | 성공 창/시간 |
|---|---|
| 17시 | 311 |
| 18시 | 278 |
| 19시 | 533 |
| 20시 | 219 |
| 21시 | 150 |
| 22시 | **0** |

- 세 키가 각각 **498 / 496 / 497** 성공 콜에서 `INFO-300`(유효 호출건수 초과)으로 멈췄다 — **일일 한도 약 500콜/키**. 3키 = 하루 1,500창, 피드는 2,047창. 하룻밤엔 산술적으로 안 들어간다.
- 창 1,495에서 패스 사망, 원장은 옛 행 그대로 — 전부-아니면-전무 계약이 지켜졌다.
- `INFO-320`(시간당 100회)이 아니라 `INFO-300`이 벽이었다. 7일 증분(`LAST_UPDT_DTM`)은 전량을 재현할 수 없어 탈출구가 아니다.

**포털의 INFO-000 메시지가 문을 알려줬다** — "전체 데이터를 원하시는 경우 CSV 다운로드 기능을 이용해 주십시오".

| 요청 | 응답 |
|---|---|
| `GET /api/{key}/I0460/file` | **200** `application/gzip`, `I0460.csv.gz` 62.8MB, **3~4초**, 2,046,504행 × 같은 12컬럼 |
| 연속 2회마다 | **429** + XML `INFO-500` (현재 접속 중인 인증키) — ~40초 후 회복 |
| 하루 11번째 | **429** + XML `INFO-330` (인증키·서비스당 1일 10회) |
| API 키가 `INFO-300`인 채로 | **200** — 쿼터가 분리돼 있다 |
| `/I0460/csv`, `/xls` | `ERROR-301` — 파일은 `data_type`이 아니라 경로다 |

- 파일 ≡ API: 기록해 둔 API 픽스처의 두 행이 파일에 **마이크로초까지 동일**하게 있다.
- **따옴표 안 줄바꿈 450건** — 줄 단위로 자르면 450행이 깨지고, 따옴표 짝이 맞는 줄바꿈에서만 레코드를 끊으면 정확히 2,046,504.
- 거부가 200 엔벌로프가 아니라 **HTTP 429**다 — 그래서 파일 작업은 엔벌로프 행도 `quota_codes`도 없고, 기존 429 재시도 경로를 그대로 탄다.

**그래서 `response_format = 'CSV'`가 생겼다** (리비전 285·286·287)

| 페이지 작업 | 파일 작업 |
|---|---|
| 창 2,047개, 5시간, 그리고 실패 | 요청 1개, **2분 7초에 2,045,467행 교체** (중복 1,037 = digest로 합침) |
| `walk_operation` → 창 | `walk_operation` → `stream` 청크 (`page_size`행) — 스테이지·잡·파생은 **무변경** |
| `execute()` → 창 하나 | `execute()` → 다운로드 결과(파일명·타입·바이트·행수) |

- 훅 `checkFileOperations`: 루트·엔벌로프·페이징 입력이 있으면 빨간색, gzip 픽스처 없으면 빨간색 — 반증 5/5.

---

# 15. 위해정보가 검사·조치 이력이 된 이유 (2026-09-20)

수거검사 원장(2,045,467행)을 파생에 올릴 때, **부적합 8,862행만** 넣는 것이 첫 모양이었다. 그게 만든 결함:

- 한 번도 수거되지 않은 제품 → "위해정보 없음"
- 12번 수거돼 전부 적합인 제품 → **"위해정보 없음"**

같은 말을 하는 두 개의 다른 사실. 규모도 작지 않다 — 우리 품목보고 중 **84,129개 제품**이 수거검사 이력을 갖는데 그중 부적합은 **1,867개 번호**뿐이다.

| 판정 | 행 | 고유 품목보고번호 |
|---|---|---|
| 적합 | 1,396,831 | 116,264 |
| 공백(미공표) | 431,947 | 29,756 |
| 상기와같음 | 111,522 | 23,273 |
| 검토중 | 96,305 | 15,695 |
| **부적합** | **8,862** | **1,867** |

**요약 컬럼은 답이 아니었다.** "수거검사 12회 · 부적합 1" 같은 숫자를 품목보고에 컬럼으로 두면 화면이 그 숫자를 받쳐줄 행을 갖지 못한다 — 읽는 쪽이 검증할 수 없는 수. 업무는 파생 테이블만 읽는다는 원칙이 그 선택을 배제한다.

**그래서 테이블 이름이 바뀌었다** (리비전 288·289)

| 이전 | 이후 |
|---|---|
| `food_item_report_event` (위해정보) | `food_safety_record` (검사·조치 이력) |
| `event_key / event_kind / event_date` | `record_key / record_kind / recorded_on` |
| 부적합만, 9,814행 | 전 판정 + 조치, **2,046,422행** |
| — | `judgment`(포털 낱말) + `judgment_code`(우리 코드) |

- **소견과 조치는 한 테이블, 구분은 컬럼.** 회수 377건 중 106건은 검사와 무관하다(무등록 제조 17, 영업등록 없이 제조 12) — 그래서 이름이 수거검사 이력이 아니라 검사·조치 이력이다. 검사부적합 82건 중 67건(82%)은 같은 제품의 수거검사 부적합에 이어지는 처분이라 **나란히** 남긴다.
- **판정은 두 컬럼이다.** 포털 낱말은 한글 데이터라 화면 코드가 분기할 수 없다(리터럴은 i18n 위반이고, 번역하면 거르던 행과 안 맞는다). `judgment_code`(failed/passed/pending)로 거르고 세고 칠하며, 보여주는 것은 `judgment` 원문이다. 상기와같음은 passed, 공백은 pending.
- **미매핑은 저장하고 읽을 때 거른다.** 2,046,422행 중 제품에 닿는 것은 **473,385행**. 나머지 1,573,037행은 테이블에 있고 API가 기본으로 뺀다 — `mapped=false`로만 보인다.
- **요약은 서버가 전체를 센다.** 처음엔 화면이 가진 페이지에서 셌는데, 그러면 부적합이 1페이지에 있는 제품의 2페이지가 "부적합 0건"이라고 말한다. `failed_record_count`·`last_recorded_on`은 제품의 **모든** 행을 센 값이다.
- **포털의 HTML 이스케이프는 파생에서 푼다.** 사유 27,160건·제품명 2,862건·업소명 2,737건이 엔티티를 달고 있었다(`&#39;` 16,468, `&middot;` 8,988). 원장은 전선의 사본이라 그대로 두고, 읽히는 표에서 푼다 — 재작성 후 0건.

**라이브 증명**: 파생 21분, 2,046,422행. 연돈카레(20170433732471) 제품 카드에 `총 2건 · 부적합 1건 · 최근 2026-09-10`, 그 아래 20260825 부적합(민원관련 수거검사)과 20260910 판정 전(기타 일상수거검사).

---

# 16. 조용히 아무것도 안 되는 결함 (2026-09-20)

검사·조치 이력을 세운 다음 날 사용자가 짚었다: **"건강기능식품은 맵핑이 실패한다."**

| | 값 |
|---|---|
| 품목보고번호를 들고도 제품에 못 닿은 기록 | **18,536건** |
| 그 고유 품목보고번호 | **5,648개** |
| 전부 어느 등록부인가 | **건강기능식품(I0030) 하나** |
| 번호 충돌 | 0건 (국내 ∩ 건강기능 = ∅) |

원인은 한 줄이었다 — `FoodSafetyRecordService._registry()`가 국내·축산 **두** 원장만 읽었다. `food_item_report`는 네 등록부로 파생되는데.

**왜 게이트가 다 초록이었나**

- 쓴 값(`domestic`, `livestock`)은 전부 CHECK가 허용하는 합법 값이었다
- edge는 (report_kind, item_report_no) 두 컬럼으로 정확히 선언돼 있었다
- 테스트도 통과했다 — 두 등록부만 넣고 두 등록부를 확인했으니까
- **비교 대상이 없었다**: 같은 일을 하는 형제 파생(`barcode`, `nutrition`)은 세 등록부를 나열하는데, 아무도 그 셋을 서로 맞춰보지 않았다

이 결함은 **터지지 않는다**. 행은 들어가고, 키도 들고 있고, 읽기 계층이 "제품을 지명하지 않는 행"으로 조용히 거른다. 읽는 사람만 없어진 걸 모른다.

**그래서 하네스가 형제를 비교한다** (`check-backend-relations`)

```python
REGISTRIES = (                      # 세 파생이 모두 같은 모양으로 선언
    (FoodLedgerItemReport, DOMESTIC_KIND),
    (FoodLedgerLivestockItemReportRawMaterial, LIVESTOCK_KIND),
    (FoodLedgerHealthFunctionalItemReport, HEALTH_FUNCTIONAL_KIND),
)
UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "번호가 우리가 만드는 digest다"}
```

기대 집합은 **파생들이 나열한 것의 합집합**이다. 하나라도 빠지면 빨간색이고, 빼는 것은 이유와 함께 선언해야 한다. 수입식품은 상시 예외다 — 그 번호는 우리가 만드는 digest라 어떤 공표 기록도 들 수 없다.

**첫 설계는 뚫렸다 — 심어서 알았다.** "형제들이 나열한 것의 합집합"을 기대치로 삼고, `REGISTRIES` 상수가 있는 파일만 비교했더니:

| 심은 변형 | 1차 설계 | 최종 |
|---|---|---|
| A 인라인 `for … in ((A,x),(B,y)):` — **어제 실제 모양** | **통과** | FAIL |
| B 형제 전부가 같은 등록부를 함께 빠뜨림 | **통과** | FAIL ×4 |
| C 한 줄 튜플 | **통과** | FAIL |
| D 조회 결과를 지역 변수로 옮김 | **통과** | FAIL |
| E 예외 선언만 지움 | FAIL | FAIL |
| 없는 원장을 선언 | FAIL | FAIL |

세 가지를 바꿔 막았다:

- **진실은 형제 합의가 아니라 소유자다.** 기대 집합은 `item_report.py`가 제품을 파생하는 원장들이다 — 그래서 B(모두가 함께 잊음)가 잡힌다.
- **조회는 이름이 아니라 시그니처로 찾는다.** `async def _registry(self) -> dict[str, str]:` — 번호→등록부 맵을 돌려주는 것만. `item_report_ingredient`의 `_registry()`는 원재료 색인(`_Registry` 반환)이라 오탐이었고, 이 시그니처는 그것을 제외한다.
- **튜플은 괄호를 세어 읽는다.** 줄바꿈에 기대면 한 줄로 쓴 순간 그 파일은 검사에서 사라진다 — 아무것도 매치하지 않는 파일은 "통과"로 보인다.

강화하자 **실트리에서 같은 형태가 셋 더** 나왔다: `barcode`·`nutrition`·`label_family`가 수입식품을 주석으로만 설명하고 있었다 → 셋 다 `UNRESOLVED_REGISTRIES` 선언으로 올렸다.

**그리고 남은 한계 ①을 바로 고쳤다 — 그게 같은 결함이었으니까.** `food`를 상수로 적은 검사는, 두 번째 도메인이 생기면 *보이지 않아서* 통과시킨다. 한 단계 위에서 똑같은 모양이다. 그래서 훅은 도메인을 **발견**한다:

| 상수였던 것 | 발견하는 방법 |
|---|---|
| 도메인 폴더 | `models/` 아래에서 `__tablename__ = "<폴더명>_ledger_…"`를 가진 폴더 |
| `FoodLedger*` | 폴더명 PascalCase + `Ledger` |
| 소유자 `item_report.py` | `NATURAL_KEY`가 정확히 (구분, 번호) 두 칸이고 `CheckConstraint`가 구분을 닫는 파생 테이블 |
| 제품 간선 | 그 소유자의 클래스와 두 키 칼럼 |

발견이 실제로 찾은 것: `domains: ["food"]`, `owner: item_report.py (FoodItemReport, report_kind, item_report_no)` — 손으로 적었던 상수와 같은 값을, 이번엔 트리에서.

**침묵마다 경보를 달았다.** 발견이 실패하면 검사는 "깨끗한 트리"와 구별되지 않는다:

| 심은 변형 | 결과 |
|---|---|
| G 두 번째 도메인(pharma), 정상 | PASS — 오탐 없음 |
| H 두 번째 도메인이 등록부를 빠뜨림 | FAIL |
| I 두 번째 도메인의 원장이 간선을 선언 | FAIL |
| J 소유자의 `CheckConstraint` 문구 변경 | FAIL "비교할 소유자가 없다" |
| K 소유자의 `NATURAL_KEY`를 한 칸으로 | FAIL 〃 |
| M 다른 테이블이 같은 모양을 가짐 | FAIL "둘 중 어느 쪽인지 모양으로 못 고른다" |
| L 원장이 도메인 폴더 밖에 | FAIL |
| N `pharma_ledger_*`가 `models/food/`에 | FAIL |

M이 실제 위험이었다: 처음엔 "두 칸 **이상**"으로 찾아서 `food_standard`(5칸)·`food_item_report_ingredient`(3칸)도 후보였고, 디렉터리 순서가 소유자를 정하고 있었다. **정확히 두 칸**으로 좁히고, 그래도 여럿이면 추측 대신 그 사실을 보고한다.

**남은 한계**: 기대 집합은 소유자가 언급하는 모든 `<Domain>Ledger*`이라, 그 서비스가 등록부 아닌 원장을 읽으면 형제들이 선언을 하나 더 써야 한다 — 침묵이 아니라 **소음** 쪽으로 틀린다. `item_report_declaration`의 `PRODUCTION_SOURCES`는 (원장, 구분, 등록부) 3요소로 같은 일을 하는데 `_registry()`가 없어 여전히 이 검사 밖이다.

- 일반화의 축은 "값이 합법인가"가 아니라 **"소유자가 아는 것을 나도 아는가"**다.

**고친 뒤**: 파생 재실행 21분, 제품에 닿는 행 473,385 → **491,921**, 번호는 제품인데 안 닿는 행 18,536 → **0**.

---

# 17. 안 붙는 행의 해부 — 그리고 범위 (2026-09-20)

사용자가 물었다: **"매일맛있는진간장골드는 수거검사 이력이 없는 거야?"** 등록부에는 있는 제품인데
(포털 I1250이 1건으로 응답) 검사·조치 이력이 0건이었다. 제조사는 254건 잡혀 있었다.

**이름으로 붙이자는 유혹을 재보고 버렸다.** 수거검사 원장 2,045,467행을 번호 기준으로 쪼갠 값:

| 부류 | 행 | 진단 |
|---|---:|---|
| 번호 없음 | 1,378,492 (67.4%) | 업종이 답이다: 제조업 3.3% 빈칸 vs 음식점·판매업·수입판매 ~99% 빈칸 — 그 업종엔 품목제조보고번호가 존재하지 않는다 |
| 번호 있고 붙음 | 491,678 | — |
| 번호 있는데 안 붙음 | 175,297 | 아래 두 줄 |
| … 다른 원장이 아는 번호 | 106,988 | 바코드 14,354 · 영양성분 5,145 · 생산실적 4,812 · HACCP 3,449 · 건기식 생산 2,990 · 축산물 생산 826 (고유번호 22,853) |
| … 어디에도 없음 | 68,309 | 위생용품 8,311(I2711이 20/20 보유) · 축산물 ~14,000 · 식품제조 36,878 |

**등록부가 낡은 게 아니다** — 포털 I1250 총계 1,074,927 vs 우리 원장 1,074,179(정상 드리프트), 그리고
"다른 원장이 아는" 번호 12개를 포털에 직접 물으니 **0/12**. 품목제조보고는 **현재 유효한 보고만** 공개하고,
바코드·생산실적·HACCP 원장은 이력을 남긴다. 표본이 성질을 말해준다: `양파링HOT&SPICY(반제품)`,
`수출라이스누들 알프레도` — 폐지·반제품·수출용.

**판단(사용자): 품목제조보고에 없는 제품은 관리 대상이 아니다.** 그래서 이 세 덩어리는 전부 원장에만 남는다.
제품 정체성을 이력 원장으로 넓히지 않고(제품 테이블의 뜻이 "유효한 보고"에서 "관측된 적 있는 품목"으로
바뀐다), 식품이 아닌 위생용품 등록부(I2711)도 들이지 않는다. 도달률 91%는 **선택하지 않은 상한**이지
미달이 아니다.

그리고 처음 질문의 답: 그 제품은 정말로 수거된 적이 없다. 화면이 맞게 말하고 있었다.

---

# 18. 국가는 바코드로 사건을 잇지 않는다 — 수입은 신고 건이다 (2026-09-20)

"수입식품은 검사·조치 이력이 없는데 원장으로 쓸 게 있나"에서 시작해 바코드로 오래 팠다. 잰 값:

| 축 | 제품 도달 | 판정 |
|---|---:|---|
| 식약처 바코드 C005·I2570 | **3.4%** (국내 4.9 · 축산 1.4 · 건기식 12.8 · 수입 0) | 코리안넷 유료 DB의 **2018년 동결 사본** — 포털 공식 문구, 2021년부터 연 2만→5천→884→228 |
| 코리안넷 표준DB | 품목보고번호 O, 수입 O | GTIN 건당 유료 |
| 이름 짝 | 수입 사건 85,526행 중 6,648(7.8%), 30% 모호 | 불가 |
| **수입신고 건** | — | **국가가 실제로 쓰는 축** |

**증명.** impfood 수입식품조회에서 (주)태양무역 목이버섯 신고 6건을 하나씩 열었다. 회수는 `rcno 202600444218`
(처리 06-25, 소비기한 05-26~) **한 건에만** 걸려 있고, 나머지 다섯은 비어 있다. 회수 원장의 `제조일자 (포장일자)
2026.5.26` = 그 신고의 소비기한 시작일. 국가는 제품이 아니라 **로트**를 회수한다.

그리고 그 신고 건은 이미 우리 원장에 있었다 — 우리가 쓰는 API가 `IprtFoodPrdtKoreanLabelingText` =
**"수입신고별"** 한글표시사항이고(`…Item` = 제품별은 따로 있다), `food_item_report_declaration`의 `D…` 키가
`(처리일자, 소비기한)`을 이미 담고 있다. 접수번호만 안 올 뿐 행은 1:1이다.

**규칙**: 번호 없는 사건은 `(수입업체, 로트일자)`로 신고 원장을 찾고, 이름이 하나를 고르거나 로트에 제품이 하나일
때만 붙인다. 날짜 있는 미매핑 회수 80건 중 신고가 있는 15건 → 정확일치 13 · 로트유일 1 · 모호 1(같은 업체가
`냉동 흰다리새우살`/`냉동흰다리새우살`로 따로 신고). 범위·`데이터없음`은 NULL.

저장하는 건 `lot_date` 한 칸. 신고 행은 읽을 때 `(item_report_no, lot_date = expiry_from)`로 찾는다 —
수입신고 이력 탭에 "어느 신고에 사건이 붙었나" 배지, 검사·조치 탭에 로트 칩.

**실행 결과(파생 재실행, 22분)**: 수입 사건 **30건**이 제품에 붙었다 — 회수 28 · 검사부적합 2. 탐침 때 15로 봤던 건 업체명을
12자로 잘라 `LIKE`로 찾은 탓이다; 파생은 정확 일치로 찾고 검사부적합 원장도 함께 본다. (주)태양무역 목이버섯의 신고
22건 중 `20260625` 한 행에만 `회수 2등급` 배지가 붙고, 검사·조치 섹션은 `로트 2026-05-26`을 보인다 — impfood가 신고를
하나씩 열어야 보여주는 것을 한 표에서 본다.

부수 발견: 신고별 API의 `OVSMNFST_NM`이 **포장재 업체**를 주는 행이 5만(5%)이다(`PLASTIC` 20,728 ·
`GLASS` 14,949 · `HARDWARE` 7,878). impfood는 같은 신고에 `HUBEI PIAOYANG FOOD`를 보여준다. 제품 키에서 빼면
63,186건이 뭉개지고 오염으로 갈라지는 건 1,266이라 키는 그대로 둔다 — 사건 매칭은 이 칸을 안 쓴다.

---

# 19. 이력 탭은 하나가 아니었다 (2026-09-20)

한 제품이 두 모양을 함께 가진 경우: **0건**. 그런데 화면은 한 탭, 한 표, 7칸이었다.

| 구분 | 모양 | 행/제품 | 연도 |
|---|---|---:|---|
| 수입식품 292,727 | 수입신고(사건) | 평균 **3.6**, 최대 1,223 | — |
| 국내 제조 886,493 | 생산실적(집계) | **정확히 1** | 2025만 |
| 축산물 12,397 (제품의 2.2%) | 생산실적 | 1 | 2016만 |
| 건강기능식품 41,801 | 생산실적 | 1~**10** | 2016~2025 |

그래서 모든 행의 3~4칸이 `—`였고, **국내 제품 탭에도 "수입신고 이력"이라는 제목**이 붙어 있었다 — 국내는 수입신고를
하지 않는다. 구분이 탭 이름·제목·칼럼을 고르게 바꿨다: `수입신고`(6칸) / `생산실적`(3칸), 빈칸 0.

**조치 칼럼은 수입 표에만 둔다.** 회수는 한 건의 통관에 걸리고, 생산실적은 한 해의 수치다 — 집계에는 조치가 걸릴
자리가 없다. 연도가 같다는 이유로 붙이면 인과 없는 두 사실을 한 줄에 세우는 것이다. 비대칭이 어색한 게 아니라,
신고하는 대상이 비대칭이다. 같은 이유로 생산실적 표에서 `신고키`도 뺐다(신고가 아니다).

**수입량은 없다.** 수입신고별 한글표시사항 12칸에 중량·수량이 없고, 포털의 수입 물량은 국가·품목별 무역통계로만
공개된다(`수입식품 국가별 수입 현황`, `수입식품 허가 정보`). 생산실적은 제조사가 품목별로 내는 법정 신고이고 수입엔
그 제도가 없다. 수입 쪽의 양적 정보는 **신고 횟수**뿐이다.

---

---

# 20. 생산실적 셋을 파일로 — 두 피드가 처음 완주했다 (2026-09-20)

"생산실적도 파일로 오나?" → 셋 다 온다. 그리고 원장과 대조하니 **둘은 완주한 적이 없었다**.

| 서비스 | 파일 | 레코드 | 전 원장 | 후 원장 | 연도 |
|---|---:|---:|---:|---:|---|
| I0310 건기식 | 5.8 MB | 316,747 | 316,746 | 316,746 | 2016~2025 (그대로) |
| I1420 축산물 | 41.8 MB | 3,397,141 | **29,345** | **3,394,218** | 2016 → **2016~2025** |
| I0300 식품 | 123.8 MB | 7,927,213 | **1,034,296** | **7,897,240** | 2025 → **2016~2025** |

페이징으로 I0300은 7,928창, I1420은 3,398창이다. 하루 약 500콜/키 앞에서 완주가 산술적으로 불가능했고, 그래서
한 해치만 남아 있었다. 파일로는 **30초 · 143초 · 364초**.

**품질 대조(I1250으로 먼저 확인)**: 칸 18개 이름까지 동일, 같은 품목보고번호를 양쪽에서 뽑아 18칸 전부 일치,
레코드 수 1,074,927 vs API total 1,075,033(0.01% 시차). 파일은 같은 원본의 다른 문이다.

**함정 하나**: 파일의 *줄 수*는 레코드 수가 아니다. I1250은 1,378,847줄 / 1,074,927레코드 — 성상·용법 칸에 든
줄바꿈 때문에 28% 부풀어 있다. 줄로 세면 "파일이 30만 행 더 많다"는 오답이 나오고, 줄로 파싱하면 레코드가 깨진다.
운영 코드는 `_RecordCutter`(RFC 4180)로 자른다.

**전환하며 드러난 결함 둘**(둘 다 I1420이 처음 밟았다):

1. **소비자 속도가 연결을 끊는다.** 1,000행마다 스테이징하면 읽기가 멈추고 Apache가 연결을 닫는다 — 잡에서 126초
   만에 죽었는데 `execute`(최대 속도)는 같은 파일을 42초에 통과했다. 이제 `SpooledTemporaryFile`로 **선입수 후절단**한다.
2. **끊긴 몸통에 상태코드를 적었다.** `UNREACHABLE`인데 200을 함께 기록해 `ck_integration_call_answered`가 거부했고,
   **피드가 아니라 로그 때문에** 패스가 실패했다. 상태 없는 기록으로 고쳤고, 그 불변식을 테스트에 박았다.

**파생 영향**: 선언 2,150,541 → **8,269,122행**, 파생 21.8분 → **27.8분**. 화면에서는 한 줄짜리 생산실적 표가
10년 추이가 됐다 — `매일맛있는진간장골드`의 2016~2025 생산량이 그 자리에 있다.

---

# 21. 수입신고는 제품이 아니라 통관이다 — 브로콜리(신선) (2026-09-21)

"수입 제품의 식품유형이 국내와 같은가?" 브로콜리로 보면:

| 국내 (품목제조보고) | 수입 (수입신고) |
|---|---|
| 과.채가공품 265 · 즉석조리식품 236 · 영유아 이유식 206 | **브로콜리(신선) 145** · 과.채가공품 95 · **브로콜리(냉동) 47** |

국내 유형은 식품공전 분류("무엇으로 규제되나"), 수입의 `브로콜리(신선)`은 HS 품목명("무엇을 들여왔나"). 같은 칼럼에
**다른 두 어휘**다. 신고구분별로 우리 어휘(국내·축산·건기식 유형 1,329개)와 대조:

| 신고구분 | 신고 건 | 유형 | 어휘 일치(건) | 정체 |
|---|---:|---:|---:|---|
| 가공식품 | 473,886 | 508 | **95.3%** | 식품공전 유형. 나머지는 커피 4종(16,585건)과 복수 유형 나열 |
| 식품첨가물 | 67,532 | 544 | 81.5% | 〃 |
| 건강기능식품 | 28,574 | 1,103 | 48.4% | 〃 (수입 표기가 길다) |
| 축산물 | 155,929 | 459 | 19.2% | 검역 분류 `돼지고기(냉동,정육(뼈없는것),…)` |
| 기구·용기·포장 | 177,302 | 1,878 | 2.4% | **식품이 아니다** |
| 농·임산물 | 80,398 | 542 | 0.001% | HS 품목명 |
| 수산물 | 71,028 | 1,053 | **0%** | 〃 |

**판단(사용자): 위 셋만 제품이다.** 원장은 전체(일곱 구분 1,054,649건)를 그대로 두고, 파생이 `PRODUCT_DECLARATION_KINDS`
(가공식품·식품첨가물·건강기능식품)만 읽는다. 하나의 상수를 여섯 독자가 `scan_table(where=)`로 나눠 쓴다 — 제품·신고·라벨·원재료,
그리고 사건이 로트를 찾는 색인.

| | 전 | 후 |
|---|---:|---:|
| 수입 제품 | 292,727 | **168,629** |
| 수입 유형 어휘 | 6,066 | **2,134** |
| 수입 신고(파생) | 1,054,649 | **569,992** |
| 수입 사건(제품 도달) | 30 | **13** |

사건이 30→13으로 준 것은 손실이 아니라 정합이다: 빠진 17건은 목이버섯·냉동리치·벌집꿀 같은 **농·수산물 원물**의 회수였고,
원물은 더 이상 제품이 아니니 붙을 곳이 없는 게 맞다. 원장에는 그대로 있고, 사건 목록은 `mapped=false`로 여전히 읽힌다.

**남는 것**: 가공식품 4.7%의 불일치는 어휘 차이가 아니라 커피(볶은커피 13,984 등 — 공전 유형인데 국내 등록부에 우연히 없음)와
`복합조미식품, 향미유, 유탕면`처럼 한 신고에 유형이 여럿 적힌 경우다. 후자는 정규화 후보지만 데이터가 아니라 규정 해석이라 손대지 않았다.

---



# 이 덱의 사용법

<div class="lead">규칙은 현재 계약, 덱은 그 계약이 서게 된 숫자</div>

- `.omp/rules/*.md` 에는 **지금 지켜야 할 것**과 그 근거 **한 줄**(수치 + 날짜)만 둔다.
- 폐기한 설계, 재본 대안, 라이브 증명 로그, 포털 성질 측정 — 전부 여기에 **슬라이드를 추가**한다.
- 새 측정을 하면: 슬라이드 추가 → `make build` (decks/) → `make check-decks-sync`.
- 규칙에서 한 줄 근거가 가리키는 곳이 이 덱이다: "측정: 이 덱 §3" 처럼 절 번호로 가리킨다.
