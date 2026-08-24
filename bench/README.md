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
