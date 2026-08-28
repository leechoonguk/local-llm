# bench — 결과 기록 (표준 + 인덱스)

벤치를 **수행하는** 환경은 여기 두지 않는다 — 2단계 러너·브리핑·레퍼런스는 `.claude/skills/llm-bench/`, 피험자 트리는 `sandbox/`. 이 디렉터리는 결과만 보관하며 플랫하다. 러너는 `<date>.s2.<campaign>.json` 을 여기에 직접 쓴다.

## 표준

**파일 하나 = 캠페인 하나**(같은 하네스·같은 조건으로 묶어 돌린 실행 집합). 하위 디렉터리 없음.

```
<YYYY-MM-DD>.<stage>.<subject>.md      # 사람이 읽는 기록 (필수)
<YYYY-MM-DD>.<stage>.<subject>.json    # 하네스가 남긴 원본, 있으면 같은 stem 으로 (선택, 가공 금지)
```

- `stage`: `s1` = 단발 과제(실행 채점, 필요조건) / `s2` = 실제 프로젝트 장기 에이전트 세션(충분조건).
- `subject`: 서빙-모델 또는 하네스 이름. 소문자·숫자·하이픈, 모델 버전 때문에 점 허용(`ollama-qwen3.6-coder`).
- 러너 원본 `.json` 하나가 여러 캠페인의 원본일 수 있다. 그 경우 `.md` 짝이 없어도 되지만, 어떤 캠페인 `.md` 의 출처 절이 백틱으로 그 파일명을 인용해야 한다.
- 날짜는 캠페인 시작일(UTC 기준 시각은 본문에).

`.md` 고정 절 — 순서와 제목을 바꾸지 않는다:

1. **조건** — 호스트/RAM, 서빙 스택+버전, 모델(양자화), 창/출력, thinking 설정, temp/top_p/top_k, **n**, 상한(타임아웃), 단일 로드 확인 방법. 실측이 아닌 값은 "추정".
2. **과제** — 무엇을 시켰고 무엇으로 채점했는지(기대 산출물 수, 게이트).
3. **결과** — 표. 실행 1회 = 행 1개(피벗 표 금지). 필수 열: 실행 식별(시각/#), 모델, 과제, thinking, 소요(초 또는 m분s초), 산출물/기대, 게이트, 비고. s1 은 모델이 하나여도 같은 열을 두고 게이트 열에 PASS/FAIL 을 적는다. **무효 실행은 지우지 않고 "무효"와 사유를 적는다.**
4. **판단** — 이 캠페인 안에서만 읽히는 것. n=1이면 "잠정"을 붙인다. 캠페인 간 종합은 이 README 의 "종합" 절에 쓴다.
5. **출처** — 원본 파일(같은 stem 의 `.json`), 세션 ID, 하네스 커밋.

이 표준 중 기계로 검사하는 부분은 `.claude/rules/bench-results.md`(`make check-bench-results`)에 있다. `bench/` 하위 디렉터리와 규격 밖 파일명은 훅이 쓰기 전에 막는다.

수치 규칙: 속도는 tok/s, 시간은 초를 기본으로 하고 분 표기는 병기. 산출물 수는 완성도가 아니므로 항상 게이트 결과와 같이 적는다. 개발사 자체 벤치를 인용하면 "자체 측정"이라 쓴다.

## 인덱스

| 파일 | 요약 |
|---|---|
| [`2026-08-23.s1.ollama-qwen3.6-coder.md`](2026-08-23.s1.ollama-qwen3.6-coder.md) | 단발 4과제, Ollama `qwen3.6-coder` nvfp4, 창 65536, thinking on, n=1 → **3/4**, 62~67 tok/s |
| [`2026-08-23.s2.ollama-manual.md`](2026-08-23.s2.ollama-manual.md) | 러너 이전 수동 8회. 3.6@auto 산포 극심, medium 고정으로 수렴. 3.8은 write 0 |
| [`2026-08-24.s2.ollama-matrix.md`](2026-08-24.s2.ollama-matrix.md) | 무인 매트릭스 3모델×2과제, thinking medium → 3.6 integration 6/6 완주, qwen3-coder REST 12/13, 3.8 전부 타임아웃 |
| [`2026-08-24.s2.omlx.md`](2026-08-24.s2.omlx.md) | oMLX 3.6 integration 6/6 16m40s(Ollama 19m 대비), REST 는 무제한 thinking 회귀 vs `thinking_budget` 회귀 0, 3.8 nvfp4 write 0 |
| [`2026-08-24.s2.sonnet.md`](2026-08-24.s2.sonnet.md) | 러너 검증/상한. `claude-sonnet-4-6`(클라우드)로 sandbox rest 셀 완주 — 15/13, 게이트 초록, 회귀 0, 190 writes, 10분. 파이프라인 end-to-end 실증 |
| [`2026-08-24.s2.qwen-recipe.md`](2026-08-24.s2.qwen-recipe.md) | 새 러너(단일 상주·aux 4B 고정)로 3.6:mtp(budget 5120) n=2 + oQ6:mtp n=1. 3.6 integration 2/2 게이트 초록, rest 1/2, 4런 전부 회귀 0(레시피 검증). oQ6 writes 0(배제) |
| [`2026-08-24.s2.roster.md`](2026-08-24.s2.roster.md) | 비-Qwen 로스터 5모델×2과제 n=1. 어느 모델도 양쪽 게이트 초록 못 냄. Qwen3-Coder-30B 가 최선(회귀 0, rest 14/13 미완성 1), Gemma-26B 파괴적(회귀 4), Gemma-12b-coder·Devstral 무산출(writes 0) |
| [`2026-08-25.s2.recipe-3.6-baseline.md`](2026-08-25.s2.recipe-3.6-baseline.md) | 챔피언 3.6:mtp(budget 5120) n=2 재확정. integration 2/2 게이트 초록(18m·14m, 회귀 0), rest 1/2(26m 초록 ↔ 45분 캡). REST 갭은 품질 아닌 완주 속도 |
| [`2026-08-25.s2.recipe-tb3072.md`](2026-08-25.s2.recipe-tb3072.md) | **음성결과**: 3.6:mtp thinking_budget 3072 n=2. 5120 이 압도 — integration 1/2(미관여 위양성), rest 0/2(회귀 1+캡). 사고 줄이면 REST 회귀·integration 미관여. 5120 유지 |
| [`2026-08-25.s2.recipe-rest-cap60.md`](2026-08-25.s2.recipe-rest-cap60.md) | REST 상한 45→60분 n=2. 캡 미도달(32분)인데도 미완성 1로 실패 — REST 갭은 속도 아닌 능력 경계. 5120 REST 누적 n=4=2/4 초록, 실패는 항상 미완성 1(무회귀). 상한·레시피로 100% 불가 |
| [`2026-08-26.s2.stuckreset-v2.md`](2026-08-26.s2.stuckreset-v2.md) | stuck-reset 확장(주기 12턴 컨텍스트 리셋+중립 nudge, 도메인 하드코딩 없음) REST n=2 = 1/2 초록·회귀 0, baseline 과 동률 — 표준 baking 보류. 단 리셋 4회(133→5 메시지) 맞고도 todo 기억으로 완주 — 릴레이 아키텍처 성립 실증 |
| [`2026-08-26.s2.stuckreset-v3.md`](2026-08-26.s2.stuckreset-v3.md) | v3(일반화 3레버: end-gate turn_end 재구동+자카드 thrash+정체 리셋) REST n=3 = **2/3 초록·회귀 0** — baseline(1/2)·v2(1/2) 대비 우세 추세(확인 패스 1셀은 중단, 미확정). END-GATE 평시 침묵·red 종료시만(마이크로테스트 실증). 후속은 체계화판 `ext/continuity.ts` 캠페인 |
| [`2026-08-26.s2.continuity.md`](2026-08-26.s2.continuity.md) | 체계화판 continuity 검증 + **하네스 결함 2건 실측·수정**(red-clear 무력화 버그, 마이그레이션 룰 미발화 구멍→migrate-gen 블록, thrashing 10→2). 옛 baseline 은 새 스택 비교기준으로 무효 판정, 정량 비교는 n 한계로 종료 — continuity 는 회귀 0의 메커니즘 검증된 옵트인으로 유지(baking 보류) |
| [`2026-08-26.s2.fixed-harness-baseline.md`](2026-08-26.s2.fixed-harness-baseline.md) | 룰 감사 수정(전달 Workflow·완전 체크리스트·모순 통일·룰귀속·메타검사) 후 **훅 없이 REST n=2 = 2/2 초록·회귀 0**(39.5m/41.2m) — 옛 "능력 천장(~50%)"의 상당 부분이 하네스 아티팩트였음을 시사(하네스가 달라진 비교·n=2 한계 명시) |
| [`2026-08-26.s2.fixed-harness-continuity.md`](2026-08-26.s2.fixed-harness-continuity.md) | 같은 하네스에 4신호 훅을 얹은 비교(유효 n=1) — **45m TO·writes 70**: 위생·유사도 리셋이 건강한 작업 중 churn 비용으로 작용. 훅을 "아플 때만 발동"(정체 이중트리거+end-gate) 슬림판으로 재설계해 `.omp/extensions/` 워크스페이스 내부화한 근거 |
| [`2026-08-26.s2.parity-slim.md`](2026-08-26.s2.parity-slim.md) | 슬림 훅 패리티(유효 n=1) — 훅은 완벽 침묵했으나 **busy-loop 발견**(45m TO, writes 562, green 1회뿐): "성공 변이 지속"은 건강이 아니며 건강 = green 으로의 주기적 복귀. → red-age 트리거 + 2단계 리셋(save-then-clear, 체크포인트 먼저) 재설계의 근거 |
| [`2026-08-26.s2.hygiene2p.md`](2026-08-26.s2.hygiene2p.md) | two-phase 지속형 컷 실증(유효 n=1) — 컷 후 ctx 유지·dt 2~4배 개선(70k대 12~119.7s→23k대 3.5~17s), 위생 컷 6.5s vs omp 컴팩션 48.5s. **턴수 sickness 는 구조적 결함**(빠른 턴 과발화 실측 2종→시간단독 전환, 엣지 12/12) + 컷·종료 상호작용 결함 3건 발견(green 후 컷·agent_end 재구동·파이프 가짜초록). 후속 v2 캠페인의 근거 |
| [`2026-08-27.s2.hygiene2p-v2.md`](2026-08-27.s2.hygiene2p-v2.md) | 수정 반영판 REST n=2 — **훅 메커니즘 전 항목 정당 동작**(과발화 0·가짜초록 0·정당 sick 발화만·컷 지속) 그러나 **성적 0/2 near-miss**(45m TO×2) vs baseline 2/2. 셀 #2 회귀 2(기존 서비스 `session.begin()` 제거 — additive 가드 사각). continuity 는 옵트인 유지·baking 안 함 확정, 새 사각 2건(verify 미관측 종료·소규모 edit 회귀) 기록 |
| [`2026-08-27.s2.hygiene2p-v3.md`](2026-08-27.s2.hygiene2p-v3.md) | 사각 보강판(verify-unseen end-gate + unwrap 가드), 유효 n=1 + 조기 종료 — **END-GATE red 재구동 2회 최초 실전 발화**(green 복귀 2회로 연결), 회귀 0. 그래도 45m TO near-miss(훅 셀 누적 6/6 TO) — v2 결론 유지. v2 시그니처 재현 확정 시점에 셀 #2 조기 kill(조기 종료 정책 첫 적용) |
| [`2026-08-27.s2.shiftleft-nohyg.md`](2026-08-27.s2.shiftleft-nohyg.md) | shift-left 넛지 + 위생컷 off, n=2 — **훅 셀 첫 게이트 초록**(38.5m 자체 종료, baseline보다 빠름): 넛지가 첫 verify 를 25분+→14분으로 당김. 위생컷 off 는 반증(ctx 101k·dt 308s, 컴팩션 미발화 — 컷 복원). 셀 #2 는 **스코프 가짜초록**(서브셋 green 을 게이트 green 으로 오인, 22분 조기 종료 미완성 1) — finish-gate 후보 도출 |
| [`2026-08-27.s2.rulebook-only.md`](2026-08-27.s2.rulebook-only.md) | 대조군(훅 제거, RULES 줄만), 유효 n=1+조기중단 1 — **shift-left 의 대부분은 문서 줄이 해냄**(첫 verify 16.5분) 그러나 **끝 규율은 문서로 안 됨**(red 인 채 39.6m 자체 종료, 미완성 1). 상주 continuity 패키지가 전 캠페인 공통 배경이었음도 확인. 최적안 = 문서 줄+훅 끝 규율 → exp4 |
| [`2026-08-27.s2.optimal-set.md`](2026-08-27.s2.optimal-set.md) | 최적 후보 조합(문서 줄+넛지+위생 컷+finish-gate), 유효 n=1+중단 1 — **39.7m 초록 자체 종료**: 첫 green 20.7분(역대 최속), **finish-gate 첫 실전 발화**. 단 산출물의 `75_.py`(빈 슬러그·no-op 리비전)가 **게이트 구멍**을 드러내 보강(슬러그 규칙·upgrade no-op·migrate-gen 빈 m 거부, 주입 실증) — 확정은 보강 게이트의 `optimal-set2` |
| [`2026-08-27.s2.optimal-set2.md`](2026-08-27.s2.optimal-set2.md) | 보강 게이트 재실험, 유효 n=2+중단 2 — 게이트 0/2 TO 이나 **하향 검토로 하네스·게이트·DB 무죄, 모델 분산 유죄 확정**(일탈 셀은 migrate-gen 실행 0회). finish-gate 가짜완료 폭로·넛지·컷 재현. 발견: 2단계 import 스왑 우회(verify 가 잡으므로 가드 보류), 조기킬 스냅샷 오판 교훈, `addopts` 커버리지가 서브셋 pytest 까지 물어 싼 반복 불가 → 워크플로 속도 트랙의 근거 |
| [`2026-08-27.s2.workflow-speed.md`](2026-08-27.s2.workflow-speed.md) | 속도 레버 2종(verify-fast·Exemplar Map), 유효 n=1 — **verify 런타임 6초 실측**(병목은 모델 측), verify-fast 채택 0. 셀은 13/13·최저 writes 33 의 최상 형태로 45m TO(종반 테스트 수렁). finish-gate 3번째 실전 발화(http 누락 폭로) |
| [`2026-08-27.s2.test-companion.md`](2026-08-27.s2.test-companion.md) | 레이어-테스트 동행 지시, n=0 관측 판정 — **문서 지시 2연속 무효**(동행 미발현·verify-fast 0회) → 지시 제거(`340bcf8`). import 훼손 3번째 우회(bash sed) 기록 — 순서 강제는 훅/구조 레벨이어야 한다는 가설 |
| [`2026-08-27.s2.coder-4bit.md`](2026-08-27.s2.coder-4bit.md) | 4bit(+MTP-4bit) 실험, 유효 n=1 — **기각, 5bit:mtp 유지**: 웜 70.2 tok/s(5bit 75~80 동급 이하), 45m TO 그대로 + 회귀 1(env.py user import). 배선 3전 수확: omp models.yml 등록 필수, oMLX 프로파일 별칭 default 한정(bare id+apply 우회), admin /reload 라우트 드랍(셔틀 재시작 필요) |
| [`2026-08-27.s2.zerobase.md`](2026-08-27.s2.zerobase.md) | **제로베이스 재설계 판 — 훅 최초 2/2 게이트 초록(보강 게이트)**, 셀 #1 **21.2분 역대 최속**(자발 verify 9.2분, 넛지 전부 침묵=건강 비용 0 실증) + 셀 #2 초록 트리 캡(넛지·finish-check 개입 셀). 재현성 2차 포함 완주 2/3, **TEST-NUDGE 첫 실전 발화→테스트 3종 생성**(셀3), env.py 등록 소실 4번째 → REG-WATCH 후속. 5원칙 재작성 |
| [`2026-08-27.s2.regwatch.md`](2026-08-27.s2.regwatch.md) | REG-WATCH 판 첫 묶음, n=0+정책 중단 — **묶음 조기종료 정책 첫 정식 적용**(32.5분 red 수렁 판정, 12.5분 절약). REG-WATCH 무해 확인(발화 조건 미발생), 다음 개선: agent_end 해제 후 위생 기준선 리셋(ctx 125k 팽창 대응) |
| [`2026-08-27.s2.openingbrief.md`](2026-08-27.s2.openingbrief.md) | 첫 턴 OPENING-BRIEF(최속 셀 레시피 선행 주입), n=2 — **오프닝 유도 성립·재현**: 첫 verify 분포 9.2~26분+ → **7.2/7.4분 수렴**, 셀 #1 초록 26.2m(역대 2위). 셀 #2 는 동일 오프닝에도 종반 커버리지 수렁 TO(1/2) — **종반 분산은 오프닝 독립 변수**, 신호 축 소진 임박·운영 재시도가 실용 대안 |
| [`2026-08-27.s2.retrypolicy.md`](2026-08-27.s2.retrypolicy.md) | 재시도 운영 정책 첫 묶음(1차+재시도), 음성 — 2회 모두 near-miss 실패(99.88% 캡·23.9m 미완성 1 종료). 부검 수확 2건: **REG-WATCH 입력 트리거 미스**(실셀 침묵, 수정=결과 콘텐츠 기반 트리거) + **finish-check 상한 1→2**(단일 체크 소진 후 종료 통과). 정책 기대는 유지, 표본 누적 필요 |
| [`2026-08-28.s2.advmatrix.md`](2026-08-28.s2.advmatrix.md) | 어드바이저 조합 매트릭스(작은 코더+강한 감시자) — **기각(사용자)**: MoE 속도 역전(35B 최속 손 75-80 vs 9B 41-44·4B+MTP 45.3 tok/s)으로 전제 붕괴, 조언이 실전급이어도(usage 23·concern 실물) 약한 코더는 실행 불능. **부산물**: 어드바이저 헤드리스 실동 확정(과거 "무동작"은 키 오류), oMLX 전면 포팅·admin API 다운로드 절차, 4B MTP 페어링 |
| [`2026-08-28.s2.final.md`](2026-08-28.s2.final.md) | **프로그램 종결 결산**(유효 n=0 — TAIL-TRIM 오발 무효 1 + 사용자 중단 1): 단발 45분 초록은 3.6 밖(풀링 scored 20%·게이트@50m 40%·회귀 0/10), 하네스는 비병목·품질 바닥 완성(Sonnet 2/2 실증). **운영 권장 = 통합 하네스 + budget 2048 + 재시도 SLA**. 어드바이저 매트릭스는 준비 완료 상태로 보류 |
| [`2026-08-28.s2.frontier2p.md`](2026-08-28.s2.frontier2p.md) | Sonnet 기준선·2단계 분해 검증 — **Sonnet 2/2 scored 초록(7.9/8.9m, 회귀 0, 신호 1발): 하네스 비병목 최종 실증**. two-phase 메커니즘은 정상([387,189])이나 3.6 본 실험 첫 표본 TO([1500,1500] 양 캡 소진) — 2단계 기각, 분산의 원천은 컨텍스트가 아니라 모델 물리 |
| [`2026-08-28.s2.valblock.md`](2026-08-28.s2.valblock.md) | 통합 스택 검증 블록(사전 등록 목표: 단발 ≥5/6·중앙값 ≤35m·운영 100%·회귀 0) — **번들 2에서 단발 목표 산술 사망, 사용자 중단**. 풀링 실증(n=10): scored 20%·게이트 초록@50m 40%, **초기 2/2들은 전부 꼬리**(순서통계 경고 실증). 품질 바닥(회귀 0/10)은 완성 — 남은 분산은 모델 물리. 다음 갈림길: 2단계 분해 vs 종결 선언 |
| [`2026-08-28.s2.thinkbudget.md`](2026-08-28.s2.thinkbudget.md) | 모델 설정 축 첫 스윕(러너 오버레이, 2단 실효 검증) — **budget 2048 승자**(2/2 초록, 유일 scored green 38.6m), 1024 하한 초과(게이트 회피→TO+미달), max4096 무이득 기각(운영 기본 8192 유지). 부산물: preflight 타깃·EISDIR fail-open 원칙·edit 전멸 부검(~10m 낭비 수정) |
| [`2026-08-28.s2.refrozen.md`](2026-08-28.s2.refrozen.md) | 게이트-압박 번들(하드 finish-block·edit-count 케이던스) 첫 실전 — **발화 전부 검증**(finish-block 이 가짜완료를 실전 차단, 첫 게이트 5.0~9.4m), 그러나 초록률 1/4 = 이전 널 대역 → **사용자 결정으로 조기 종료·축 전환**(thinking budget 스윕). 하네스는 확정·동결 선언 |
| [`2026-08-28.s2.frozen-null.md`](2026-08-28.s2.frozen-null.md) | **동결 설정 널 분포 첫 측정**(n=8, 하네스 무수정, 캡 3600s 관측·채점 green@2700) — **p̂=1/8(12.5%), Wilson CI [2.2%, 47.1%]**. 캡 연장 무효(green@3600도 1/8), near-miss(미완성 1)가 실패 6/7, **회귀는 8셀 전부 0**(REG-WATCH 콘텐츠 트리거 6발 — 회귀 클래스 소멸). 어제의 초록들은 분포 꼬리로 판명 |
| [`2026-08-27.s2.gatefix.md`](2026-08-27.s2.gatefix.md) | 부검 수정 2건(`1ffff0c`) 위 재시도 묶음, **첫 양성** — 1차 게이트킬 32.4m(**REG-WATCH 콘텐츠 트리거 첫 실전 발화**: conftest user import 소실 즉시 감지) → 재시도 **33.3m 초록**(회귀 0·미완성 0, END-GATE 재구동 ×2 가 red 종료를 되돌려 마감 견인). 궤적>스냅샷 재확인(32.2m red → 1분 뒤 초록). 재시도 정책 누적 1/2 묶음 성공 |

원본: `2026-08-23.s1.ollama-qwen3.6-coder.json`(s1 summary), `2026-08-24.s2.llm-bench-runner.json`(러너 `results.json` 7행 — 08-24 매트릭스·oMLX·3.8 재시도 포함, 누적 기록 수정 `1350c98` 이전 셀은 없음).
README(루트)에 있는 08-20 oMLX vs Ollama 단발 비교, 3.8 양자화 속도, `reasoning_effort`/`thinking_budget` 실측은 벤치 캠페인이 아니라 설정 실측이라 여기 두지 않는다.

## 종합 (2026-08-24 기준, 셀당 n=1 — 전부 잠정)

1. **oMLX 전환은 손해가 아니다.** 같은 3.6·같은 창·같은 과제로 integration 완주 16m40s vs Ollama 19m. 단 thinking 조건이 다르다(Ollama medium / oMLX 무제한).
2. **모델이 과제별로 상보적이다.** 규약 정밀 복제(integration)는 thinking 3.6, 정형 5계층 다량 생성(REST)은 instruct `qwen3-coder`.
3. **dense 27B(3.8)는 에이전트 루프에서 파일을 못 쓴다.** Ollama 6회 + oMLX nvfp4 1회 = 7회 write 0. 창·사고강도·`thinking_budget` 무관. oQ6(6bit)만 미측정.
4. **`thinking_budget` 은 회귀를 줄이는 방향.** 3.6 REST 무제한은 `User` 등록 삭제 회귀+타임아웃, 5120 상한은 회귀 0+자체 종료. 게이트는 둘 다 FAIL 1.
5. **산출물 수 ≠ 완성도.** 15/13 을 만든 실행이 계정 테이블 DROP 을 유도하는 상태였다. 게이트 없이 쓰지 말 것.
6. **과제 난도 차 > 모델 차.** 같은 3.6이 6/6 과 5/13.

다음: 셀당 n≥2(우선 oMLX 3.6 integration 무제한 vs budget, REST budget 재현), oMLX 쪽 instruct 코더 후보, 3.8 oQ6 1회.

## 종합 (2026-08-25 — 로스터 + 레시피 조사, 단일 상주 러너)

이날 4개 캠페인(roster·recipe-3.6-baseline·recipe-tb3072·recipe-rest-cap60)으로 "소넷급(양쪽 게이트 초록·회귀 0)" 목표를 파고들었다.

1. **챔피언은 3.6:mtp @ thinking_budget 5120 로 확정.** integration 은 반복해서 게이트 초록(baseline n=2 = 2/2, 18.0m·13.8m, 회귀 0) — 로컬 모델 중 유일하게 Mode A(규약 정밀 복제)를 안정적으로 완주한다.
2. **REST 는 능력 경계다(속도 아님).** 5120 REST 누적 n=4 = **2/4 게이트 초록**. 실패 2건은 각각 45분 캡 타임아웃과 32분 조기 종료 — 후자는 시간이 남았는데도 **미완성 1** 로 끝났다. 캡을 60분으로 올려도(`recipe-rest-cap60`) 100% 가 안 된다. 실패는 언제나 near-miss(미완성 1, 12~13/13 정답, **회귀 4런 모두 0**)로 파괴적이지 않다.
3. **레시피는 5120 이 최적 — 낮추면 악화(음성결과).** `recipe-tb3072`(budget 3072 n=2): integration 1/2(사고 부족으로 미관여 위양성), REST 0/2(회귀 1 + 캡). **사고예산이 REST 의 회귀를 막는 요소**라는 이전 실측과 일치. 기본 코더 레시피·벤치 상한(45분) 모두 변경하지 않는다(repo 불변).
4. **비-Qwen 로스터에 소넷급 없음.** 5모델×2과제 어느 셀도 양쪽 초록 못 냄. Qwen3-Coder-30B 가 최선(회귀 0, REST 14/13 near-miss)이나 사고가 없어 integration 은 미완성 3 — 기본 코더는 두 과제를 다 하는 3.6 이 우위. Gemma-26B 파괴적(회귀 4), Gemma-12b-coder·Devstral 무산출(writes 0).
5. **단일 상주(강제 언로드 + 4B aux 고정)는 20+ 셀 전 구간 `residency.ok:true`** — 러너의 admin API 방식이 모델 전환마다 정확히 대상만 상주시킴을 검증.
6. **채점 위양성은 `no_work`(writes 0)로 걸러진다.** Mode A 에서 부모 상태 잔여로 `gate 0·art 6` 이 "성공처럼" 보이는 케이스를 writes 로 판별 — 로스터·tb3072 에서 실제로 여러 건 포착.

추가 검증 후 배제(2026-08-25, 캐시·설정 삭제):
- **GLM-4.7-Flash-4bit** — integration 단발 셀이 45분 타임아웃 + 게이트 FAIL(writes 26). 관여는 하나 3.6(14~18분 초록) 대비 느리고 미완주. n=1 부분 측정에서 열등해 중단.
- **Qwen3.8 dense 27B 재검증** — arca.live reasoning-levels 글 계기로 MLX 표준 4bit + `reasoning_effort=medium`(순정)으로 재측정. integration 9분간 **writes 0**(모델 산출 없음, 러너 부모상태 세팅만). 이전 Ollama GGUF 6회·MLX nvfp4·MLX oQ6 와 동일 → **3.8 의 writes 0 은 양자화·경로·reasoning_effort 무관한 에이전트 루프 문제**로 확정. dense 라 ~3.7배 느려 코더로도 부적합. 8bit/MTP 는 미검증(4bit 재현으로 배제 결정). GGUF(Unsloth Dynamic V3.0 developer-role)는 Ollama 필요라 이번 스택(oMLX MLX 전용)에서 미검증.

**결과적으로 코더는 3.6:mtp @ budget 5120 로 확정. 모든 대안(로스터 5모델·GLM·3.8 4종)이 이 아래다.**

## 종합 (2026-08-26~27 — continuity/two-phase 트랙)

stuckreset v2·v3 → continuity 체계화 → 하네스 룰 감사 → slim/two-phase 진화(빌드 A~C → v2)까지 "세션 지속력 훅" 트랙의 종합.

1. **최대 수확은 훅이 아니라 하네스 감사였다.** 룰 전달 구멍·내용 모순·체크리스트 부재를 고치자 **훅 없이 REST 2/2 초록**(39.5/41.2m) — 옛 "능력 천장 ~50%"의 상당 부분이 하네스 아티팩트.
2. **continuity 훅의 메커니즘은 전부 실측 검증됐다**: 릴레이(리셋 생존·todo 기억), 지속형 컷(ctx 유지, dt 2~4배 개선), save-then-clear 체크포인트, 시간단독 sickness(과발화 해소, 엣지 12/12), truncated-clear 가드, 위생 컷(6.5s, omp 컴팩션 48.5s 대비 7배 저렴 + 구조화 체크포인트).
3. **게이트 개선 증거는 shift-left 도입 후에야 나왔다**: 턴수/시간단독 sickness 시대의 훅 셀은 전부 45m TO 였으나, **shift-left(문서 줄+넛지)+finish-gate 조합에서 훅 셀 첫 초록 2회**(shiftleft-nohyg #1 38.5m, optimal-set #1 39.7m — baseline 대역). 보강 게이트 재실험(optimal-set2)은 0/2 로 회귀했지만 하향 검토 결과 지배 변수는 모델 분산(일탈 셀은 migrate-gen 실행 0회). **결론: 시작=문서 줄(+넛지 백스톱), 속도=위생 컷, 끝=finish-gate 가 최적 구성이되, REST 45m 초록률 자체는 3.6 의 분산이 지배한다.** discipline 은 표준 상주(통합 패키지)로 승격, 신호는 전부 실측 검증.
4. **REST 의 실질 병목은 "45분 캡 안의 100% 커버리지"** — 훅 유무와 무관하게 마지막 1%에서 반복 캡킬. near-miss(미완성 1)가 지배적 실패형이고 회귀는 대부분 0(예외: v2 셀 #2 의 소규모 edit 회귀 2 — additive 가드 사각).
5. **사각 2건은 v3 에서 보강 완료**(verify-unseen end-gate, unwrap 가드 — 합성 15/15+8/8 실증, 실전 발화는 각각 미발생/0회로 무해 확인). 운영 교훈: 러너 셀 경계 revert 가 미커밋 하네스 수정을 지운다 — 하네스 수정은 커밋 후 캠페인. 벤치 조기 종료 정책(예측 확정 시 kill) 도입, v3 에서 첫 적용.
6. **속도 트랙(08-27 오후)의 결론**: verify 런타임은 6초라 병목이 아니고(추정 정정), **문서 지시(도구·순서)는 이 모델의 관성을 못 바꾸며**(verify-fast 0회 ×2, 동행 미발현 — 측정 후 제거), **4bit 도 벽을 못 움직였다**(웜 70.2 tok/s 동급, 45m TO+회귀 1 — 기각, 5bit:mtp 유지). 40분 벽의 남은 축은 모델 상향 또는 캡 자체의 재검토다.
7. **제로베이스 재설계~재시도 운영 트랙(08-27 저녁)의 결론**: 실측 5원칙 기반 재설계 판이 훅 최초 2/2 초록(21.2m 포함), OPENING-BRIEF 로 첫 verify 를 7.2/7.4분에 수렴시켰다(유도 성립·재현). 신호 축 소진 후의 실용 대안인 **≤2회 재시도 정책은 누적 1/2 묶음 성공**(retrypolicy 음성 → 부검 수정 2건(`1ffff0c`: REG-WATCH 콘텐츠 트리거·finish-check ×2) → gatefix 양성 33.3m 초록). REG-WATCH 콘텐츠 트리거는 첫 실전 발화로 5회 놓치던 회귀 클래스를 잡았고, END-GATE 재구동은 red 종료를 두 번 되돌려 마감을 견인했다. **하네스는 확정 구성으로 안정, 남은 분산은 재시도 표본 누적으로 흡수한다.**
8. **동결 널 블록(08-28 새벽)의 교정**: 4자 토의(분석→교차심문→투표) 합의 1순위로 실행한 첫 동결 n=8 측정이 **p̂=12.5%(1/8), CI [2.2%, 47.1%]** 를 돌려줬다 — 7항까지의 낙관(35-50% 대역 가정)은 꼬리 표본 위에 서 있었다. 캡 연장(60분 관측)은 초록을 하나도 추가하지 못했고(능력 경계), near-miss 미완성 1이 실패 6/7, **회귀 클래스는 REG-WATCH 콘텐츠 트리거 가동 후 소멸**(8셀 0건, 6발 전부 즉시 복원). 이후 개입 실험은 이 널 분포를 기준선으로 검정력을 먼저 계산한다.
