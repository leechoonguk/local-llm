---
name: llm-bench
description: 로컬 모델에게 sandbox/(최소 FastAPI baseline)의 실제 CRUD 도메인 과제를 omp 장기 세션으로 시키고 게이트로 채점한다(2단계). "이 모델을 실무에 믿고 맡길 수 있나", "모델/서빙/thinking 설정을 비교해줘", "기본 코더 바꿔도 되나"에 사용. 단발 벤치(bench-model, 1단계)를 통과한 후보에만 쓴다.
---

# llm-bench — 2단계(장기 세션) 벤치

합성 과제는 전이되지 않는다. 답할 질문은 하나다 — **이 모델이 우리 레포 규약을 지키는 단위 작업을 처음부터 만들어 낼 수 있는가**. fast-api-standard 의 하네스로 채점하되, 피험자는 그 레포를 최소로 줄인 `sandbox/` 에서 돈다. 근거 실측은 `bench/2026-08-2*.s2.*.md`.

## 구성

| 경로 | 역할 |
|---|---|
| `sandbox/` | 피험자 트리. fast-api-standard 를 **batch·user 도메인 + auth·health + core + 하네스**로 줄인 최소 baseline. 포트 분리(18000/15173/15432/16379). git 저장소 아님 — local-llm 이 추적. `sandbox/SANDBOX.md` |
| `runner.ts` | 셀 하나 = 세팅 → `omp -p` 독립 프로세스 → 하드 타임아웃 → `make verify` 채점 → 무결성 → 원복 → JSON 1행 |
| `tasks/rest_spec.md`, `tasks/integration_spec.md` | 피험자에게 넘기는 요구사항·계측 브리핑 |
| `reference/a1aebf3.{manifest.json,parent.patch}` | integration(외부 연동 추가) 레퍼런스 산출물 목록 + 부모 상태로 되돌리는 역패치 |
| `bench/` | 결과. 표준은 `bench/README.md` — 러너가 `<date>.s2.<campaign>.json` 을 쓰고, `.md` 는 사람이 쓴다 |

## 과제 두 가지

| | integration(외부 연동 추가) 재현 (`integration`) | rest(도메인 추가) 적합성 (`rest`) |
|---|---|---|
| 과제 | 외부 API I2570 을 형제 `search-food-raw-material` 을 본떠 추가 | `notice` CRUD 를 형제 `batch` 를 본떠 신규 작성 |
| 정답 | landed 산출물 6개(시드 마이그레이션 2 + `.http` + 픽스처 + 테스트 배선 2). 러너가 부모 상태 복원(레퍼런스 산출물 삭제 + 역패치)으로 숨긴다 | 없음 — 레포에 존재한 적 없어 누출 구조적 0, HEAD 에서 그대로 |
| 채점 바닥 | `make verify` = 훅 스위트 + 100% 커버리지 (**두 모드 공통**) | 동일 |
| integration(외부 연동 추가) 추가 | 레퍼런스 산출물 이름 재사용 감사(`reference_names_reused`), 시드 행 대조 | — |
| 기대 산출물 | 6 | 13 |

합격 기준이 명령으로 계산되지 않는 과제는 벤치가 아니다. 새 과제는 `runner.ts` 의 `TASKS` 에 추가하고, integration(외부 연동 추가) 면 `reference/` 에 매니페스트+역패치를 만든다(`git -C <source> diff <ref> <ref>^ -- <modified files>`).

## 절차

### 0. 전제
- 1단계(`bench-model`) 통과. 거기서 떨어진 모델은 여기서 한 시간을 쓸 자격이 없다.
- `sandbox/` 준비: `sandbox/SANDBOX.md` 의 설치 절차(uv sync, npm install, `.env` 3개, decks build). `make db-init && make verify` 가 sandbox 에서 **git 없이** exit 0 이어야 한다 — 러너도 셀마다 이걸 baseline 으로 확인하고, 빨가면 `baseline not green` 으로 셀을 버린다.
- **베이크 모드(`BENCH_BAKED=1`)**: 오버레이·`--model`·`--smol`·어드바이저 주입 없이 **라이브 설정만으로** 셀을 돌린다 — 구성 변경 뒤 "실행 경로에서 정말 먹는가"를 증명하는 용도(절차·확인 항목은 `/bake-config`). 실험 스위치(BENCH_THINKING_BUDGET 등)는 이 모드에서 무시된다.
- **셀은 무상태로 시작한다(2026-08-28 감사).** `git clean -fdq` 는 무시된 파일을 안 지워서 이전 셀의 정답이 두 곳에 남아 있었다 — `.omp/state/*.continuity.json`(지난 셀의 goal·facts·다음 행동)과 `backend` 각 레이어의 `__pycache__/notice.*.pyc`(파일명만으로 산출물 구조가 드러나고, 역컴파일하면 이전 해답 자체). 러너가 setup·revert 에서 `purgeCellResidue()` 로 지운다 — 손으로 셀을 돌렸다면 같은 정리를 하고 시작한다.
- 부모 저장소 기준 `sandbox/` 에 미커밋 변경이 없어야 한다(러너가 거부). 원복이 `git checkout -- sandbox && git clean -fdq sandbox` 라 변경이 있으면 지워진다. sandbox 안에 `.git` 이 있으면(예전 실행 잔재) 러너가 거부한다 — `rm -rf sandbox/.git`.
- **로컬 모델은 대상 모델만 상주해야 한다(러너가 보장·검증).** 세 겹이다:
  1. **시작 격리** — `omlx/` 셀은 `omlx restart` 로 서버를 비우고, `ollama/` 셀은 다른 모델을 `ollama stop`. 이전 셀 잔재 제거.
  2. **aux 역할 고정** — omp 의 `modelRoles.tiny/smol` 을 셀 동안 **실제 4B aux(`omlx/mlx-community--Qwen3.5-4B-4bit`)로 고정**한다(`--config` 오버레이 + `--smol`). 코더가 아니라 실사용 aux 로 고정하는 것 — 코더에 제목·메모리를 시키는 비현실적 구성이 아니라 실제 환경 그대로 잰다. **코더 설정(thinking·샘플링)은 불변**이고 `--model` 외 튜닝이 아니다.
  3. **구성상 보장** — 위 두 겹으로, 셀 동안 로드될 수 있는 물리 모델은 {대상 코더, 그 `:mtp` 드래프터, 4B aux} 셋으로 한정된다(compaction 도 같은 계열 `:nothink`). 엉뚱한 코더가 상주할 수 없다. 검증이 아니라 **구성**이 보장한다 — 코더(23GB)+aux(4B)가 함께 들어가려면 `iogpu.wired_limit_mb`(RAM−8GB, `omlx/install.sh` 가 부팅 지속으로 설정)가 맞아야 한다.
  4. **기록** — 러너가 상주를 실측해 행 `residency` 에 남긴다: oMLX `/health` 의 `loaded_count`·`current_model_memory`, Ollama `ollama ps`. `loaded_count` 가 예상(코더+드래프터+aux=1~3)을 벗어나면 `ok:false` 로 경고(재시작 실패·설정 누락 신호) → 재실행. 클라우드 모델은 `residency:null`.
- thinking 조건을 **명시**한다. 3.6 은 `reasoning_effort` no-op → 무제한/`thinking_budget` 중 무엇인지, 3.8 은 값이 무엇인지 `omp/models.yml` 에서 확인해 결과 `.md` 조건 절에 적는다. 러너는 `--model` 외 플래그를 omp 에 주지 않는다 — 측정 대상은 "실제로 쓰는 설정"이다.

### 1. 실행
```bash
node .claude/skills/llm-bench/runner.ts --dry-run                             # 세팅/채점/원복 점검(모델 없음, 두 과제)
node .claude/skills/llm-bench/runner.ts --model omlx/mlx-community--Qwen3.6-35B-A3B-5bit:coder --campaign omlx-3.6
node .claude/skills/llm-bench/runner.ts --models a,b --campaign <name> --timeout 2700
node .claude/skills/llm-bench/runner.ts --matrix                              # DEFAULT_MODELS × 두 과제
node .claude/skills/llm-bench/runner.ts --revert-only                         # 중단된 셀 뒤처리
```
- **기본으로 두 과제(`integration` + `rest`)를 모두 돌린다** — `--task` 를 안 주면 둘 다. 한 과제만 재려면 `--task integration` 또는 `--task rest`. 모델당 두 셀이 같은 캠페인 `.json` 에 누적된다.
- 셀당 45분 상한(실측 10~52분+). 상한 없이 매트릭스는 끝나지 않는다.
- 셀 하나에 30~45분이므로 **백그라운드로 띄우고** 세션은 다른 일을 한다. 진행 중 sandbox 의 빨간 게이트는 측정 대상이다 — **고치지 않는다**(피험자의 작업 공간).
- 피험자는 별도 OS 프로세스다. 서브에이전트로 돌리면 이 세션의 컨텍스트를 물려받고 모델 해석도 채점자 것이 된다.
- **n ≥ 2**. 같은 모델이 {6/6, 0/6, 4/6} 을 낸 전례가 있다. 모든 실행을 보고하고 최선만 고르지 않는다.

### 2. 채점 읽기 (러너 행)
| 열 | 뜻 |
|---|---|
| `artifacts/expected`, `files` | 산출물 수와 목록. **수는 완성도가 아니다** — 15/13 을 만들며 `User` 등록을 지운 실행이 있었다 |
| `gate_exit`, `gate_failures` | `make verify`. 0 산출물이면 게이트가 통과해도 실패로 읽는다 |
| `regressions` / `incomplete_failures` | FAIL 을 기존 도메인 파괴(회귀) vs 새 도메인 미완성으로 분리(휴리스틱, baseline 모델 목록 기준) |
| `asserts_removed` | 테스트에서 지운 assert 수. 0 이어야 한다 — 커버리지 게이트는 이걸 못 본다 |
| `omp_touched` | `sandbox/.omp`·Makefile 변경 수. 0 이어야 한다 — 훅을 고치면 게이트는 자명하게 초록 |
| `writes`, `tools` | 세션 로그의 write/edit 수와 툴 종류별 횟수 |
| `no_work` | `writes===0` — 피험자가 아무것도 안 썼다. **게이트/산출물 수와 무관하게 실패다.** integration(외부 연동 추가) 는 부모 상태 잔여(바코드 삭제·테스트 되돌림) 때문에 `artifacts>0·gate 0` 으로 성공처럼 보일 수 있어 이 플래그로 가른다(실측: 3.8-oQ6) |
| `residency` | 로컬 서빙 상주 상태. `single:true`(loaded_count 1)여야 유효 — `false`면 다른 모델이 같이 올라와 메모리 경합, 재실행. 클라우드 모델은 `null` |
| `turns`, `toolCalls`, `loops`, `compactions`, `peak` | continuity 상태 |

### 3. 기록
`bench/README.md` 표준대로 `bench/<date>.s2.<campaign>.md` 를 쓴다(조건·과제·결과·판단·출처). 무효 셀도 사유와 함께 남긴다. 캠페인 간 종합은 `bench/README.md` "종합" 절, 기본 코더 결정에 영향을 주면 루트 `README.md` 매트릭스와 `CLAUDE.md` 환경 사실까지 갱신한다.

### 4. 하네스 변경은 딱 한 경우
**게이트가 통과했는데 필요한 사실이 거짓이었을 때**만 sandbox 하네스를 고친다(= 구멍 실측). 고친 뒤 위반을 주입해 발화를 확인한다. 임계값·루프 상수는 벤치 하나로 조정하지 않는다. sandbox 하네스 변경은 fast-api-standard 로 되돌려 보낼 후보이지 자동 동기화가 아니다.

## 연속성 하네스 (ext/continuity.ts, 옵트인)

로컬 코더의 **작업 지속력**을 위한 omp 확장. `BENCH_HOOK=<경로>` 로 러너에 옵트인하면 셀의 omp 에 `--hook` 으로 실린다(미설정이면 기존 동작). 원칙: **도메인 하드코딩·처방 금지** — 제네릭 신호만 관측하고, 무엇을 고칠지는 모델 자율. 지속 기억은 네이티브 todo(리셋 생존, 실측), 리셋 부트스트랩이 todo 갱신을 지시한다.

- 관측(제네릭 4신호): verify red/green(bash 실패줄) · 유사 반복(자카드, 변이툴만 — read류 탐색 제외) · 정체(성공 변이 0 인 N턴) · 컨텍스트 비대(리셋 후 토큰 예산 초과 → 위생 리셋)
- 행동: 리셋(context 재작성 → [시스템+중립 부트스트랩+최근 N]) · end-gate(red 인 채 프로즈 턴이면 turn_end 재구동, 상한 2 — agent_end 시점은 teardown 으로 무효, 실측)
- 안전: 총 리셋 상한 · 같은 계열 신호 지속 시 GIVE UP(강제하지 않음) · 툴 정책 블록 제외
- 실측 계보: stuck-reset v1(동일성 감지 무용) → v2(주기 리셋, baseline 동률) → v3(end-gate+유사도+정체, REST 개선 신호) → 체계화. 근거는 `bench/2026-08-26.s2.stuckreset-v*.md`.

## integration(외부 연동 추가)(integration 재현) 재추가

무거운 integration 서브시스템이 계약 테스트와 강하게 결합돼(테스트가 시드 마이그레이션을 리플레이) sandbox 최소화 때 통째로 뺐다. 다시 하려면: fast-api-standard 에서 integration 관련 파일(models/routers/services/repositories/schemas/core integration, tests/core/test_integration*, fixtures, api/integration*.http, 훅 `check-backend-integration*`, 규칙, ast-grep integration, 시드 마이그레이션)을 sandbox 로 복원하고 포트만 치환한 뒤, `runner.ts` 의 `TASKS` 에 `integration` 셀을 되살린다. 부모 상태 복원(레퍼런스 산출물 삭제 + 역패치)은 `reference/a1aebf3.manifest.json` + `a1aebf3.parent.patch` 로 하고, 시드 마이그레이션이 다시 들어오면 마이그레이션 불변 규칙(`@{upstream}`) 때문에 임시 git 핀이 필요해진다 — 예전 러너 이력(git log)에 그 방식이 있다.

## 프롬프트 단위 사용 (2026-08-29 실측, `bench/2026-08-29.s2.promptunit.md`)

이 하네스의 최종 사용처는 40분 무인 셀이 아니라 사람이 프롬프트를 주는 인터랙티브다. 프롬프트 단위로 재보니 셀 기준 튜닝이 그대로는 안 맞았다 — 그 결과 지금 하네스에 들어간 계약:

- **피험자의 하네스 수정은 탐지로 잡는다.** 실측에서 모델이 검사 통과를 위해 채점 정규식을 고쳤다. 차단 훅은 두지 않는다(실무 편집을 막아 귀찮다 — 2026-08-29 사용자 결정). 대신 러너가 셀 종료 시 `omp_touched` 를 세어 0 이 아니면 **그 행을 무효**로 표시하고 원복 명령을 출력한다. 셀 채점 전에 이 줄을 확인한다.
- **마감 요구는 변경 규모에 비례한다**. 마지막 변경 이후 풀 게이트가 없고 변경이 ≤2파일·서 있는 경고 없음이면 `make verify-fast`/타깃 pytest 로 마감. 3파일 이상·경고 서 있음은 풀 `make verify`. (한 줄 편집에 풀 게이트 3회 → 1회, 321→220초)
- **상태는 프롬프트 경계를 넘는다**(`.omp/state/discipline.json`, gitignore·러너가 셀마다 삭제). 브리핑 1회, 게이트/경고 시각 유지. 마감 판정은 "게이트를 돌았나"가 아니라 **"마지막 변경 이후에 돌았나"**.
- **훅은 자기 경로에만 돈다**(`lib/hook-scope.ts` + `check-omp-hooks` 강제). 새 post 훅은 `touchesPath`/`touchesStrict` 를 부르거나 `// hook-scope: global — 사유` 를 단다. 도구 결과 1회 비용 bash 4.89→1.56초.
- **모델은 항상 명시한다.** 맨몸 `omp -p` 는 라이브 `modelRoles.default` 를 탄다 — 이 실측 1차 시도가 그렇게 조용히 Sonnet 으로 돌았다(세션 jsonl 의 `"model"` 로 사후 확인 필수). 베이크 모드가 아니면 `--model` 을 붙인다.
- 백그라운드 프로브는 `< /dev/null` 로 stdin 을 닫고(안 닫으면 `readPipedInput` 에서 무한 대기), 세션 인터럽트에 죽지 않게 `nohup … & disown` 으로 띄운다.

## 운영 교훈 (2026-08-26~28 프로그램 실측)

**셀 운영**
- 발진 전 `make preflight` — 셀 부재(pgrep)·sandbox 타입체크·decks 동기·루트 verify 를 한 번에 본다. 이걸 안 해서 무효 스텁이 4회 났다(TS6133, 미문서 make 타깃, decks 해시, 코드 레이아웃).
- **하네스 수정은 즉시 커밋**한 뒤 발진한다 — 미커밋 수정은 셀 경계 원복(`git checkout -- sandbox`)이 지운다(사고 2회). 원복·clean 은 **repo 루트에서** 실행한다(cwd=sandbox 면 no-op).
- 셀이 도는 중에는 하네스·설정·서버를 건드리지 않는다(스택 모호 → 셀 무효).
- **`pkill` 직후 발진 금지.** 프로세스 정리는 즉시 끝나지 않는다 — `pgrep -f "omp -p"` 가 0 이 되는 걸 확인하고 `make preflight` 가 exit 0 일 때만 띄운다. 2026-08-29 에 잔여 피험자가 살아 있는 채로 셀을 띄워 한 번 버렸다(preflight 는 정확히 그걸 경고했는데 무시했다).
- **`runner.ts --dry-run` 도 `sandbox/` 를 원복한다.** 문법 확인 용도로 부르면 미커밋 하네스 수정이 사라진다(2026-08-29 에 두 번 밟았다). 러너 문법은 사본(`cp … /tmp/x.mts && node --check`)으로 보고, dry-run 은 트리가 커밋된 상태에서만 쓴다.
- 훅로그는 셀마다 `cp` 로 보존한 뒤 비운다(로테이트 없이 지워 1회 소실).
- 검증은 **실제 종료코드**로 — `| tail`·`grep -q` 로 끝만 보면 뒤쪽 검사 실패가 묻힌다.

**조기 종료(사용자 확정 정책)**
- 판정은 스냅샷이 아니라 **궤적**으로: 같은 실패 시그니처가 10분 넘게 무진전이면 수렁(킬), 시그니처가 바뀌며 전진하면 살린다(99.5% 수렴 중이던 셀을 57% 스냅샷으로 죽인 오판 1회, 32.2m red→33.3m 초록 반례 1회).
- 30분 게이트는 **비채점 운영 판단**용이다. 채점 블록·A/B 안에서는 쓰지 않는다 — near-miss 꼬리를 검열해 분포 추정을 왜곡한다.

**통계**
- 이 게이트의 단발 초록률은 3.6-35B 기준 **scored 20% / 게이트@50m 40%(풀링 n=10)**. n=1~2 의 2/2 는 대부분 꼬리 추첨이었다(동결 널 n=8 에서 1/8 실증) — **한 판으로 설정을 판정하지 않는다**.
- 목표는 재시도를 포함한 SLA 로 잡는다(≤2회 시도, 캡 50분). "단발 45분 100%" 는 이 모델 밖이다.
- 개입 A/B 는 binary green 으로는 검정력이 없다 — 연속 지표(종료 시점 미완성 수, 첫 full 게이트 시각, 첫 초록 시각)를 1차 지표로 사전 등록한다. 러너가 `bundle`/`attempt`/`gate_runs`/`first_full_gate_s`/`first_green_s` 를 기록한다.
- 러너의 `writes`/`gate_runs` 원시값은 세션 포맷상 부풀 수 있다(도구 1회가 3레코드 + continuity 스냅샷 재포함) — 중복 제거 후 인용한다.

**하네스 신호(현행 discipline)**
- 지식은 문서로, **행동은 런타임 메시지로** — 정적 문서 지시는 2회 실측 모두 0채택이었고, 주입 메시지는 매번 작동했다.
- 파괴는 조언이 아니라 **차단**으로: 형제 치환(뼈대 같고 식별자만 다른 줄 교체) 사전 deny + `# intent: replace` 선언 시 통과. 등록 줄 소실은 REG-WATCH 가 결과 텍스트에서 감지해 즉시 복원시킨다(회귀 0/10 유지).
- **훅은 절대 던지지 않는다** — omp 는 훅 예외를 도구 실패로 승격시킨다. 가드 크래시 하나가 한 셀의 edit 을 전멸시켜 ~10분을 태웠다(fail-open 원칙).
- **세션 스코프 카운터를 신뢰하지 마라**: 확장은 셀 하나 안에서 수십~수백 번 재등록된다(실측 129회/셀, agent_end 5회) — 상한·1회성 플래그가 조용히 초기화된다. 정말 한 번만 일어나야 하는 것은 파일·경로 등 **외부 상태로 키**를 잡고, 방어는 사후 경고보다 **사전 차단**에 무게를 둔다.
- 신호를 새로 넣으면 합성 프루프(현재 50케이스)로 경계까지 검증하고, 실전 첫 발화를 부검한다. 베이스라인이 공허하게 초록인 구간(작업 시작 전)에서 오발하지 않는지 반드시 본다(TAIL-TRIM 오발로 셀 1개 손실).

**설정 축**
- 속도는 모델 설정, 품질 바닥은 하네스, 품질 상한은 모델이다. thinking budget 2048 이 실측 최적(5120 대비 우세, 1024 는 하한 초과), maxTokens 4096·2단계 분해·4bit·소형 코더 조합은 전부 기각(`bench/2026-08-28.s2.*.md`).
- 구성을 바꿨으면 `/bake-config` 절차로 굽고 `make smoke` 로 "서버가 그 값을 인정했는지"까지 확인한다.

## 하지 말 것
- 벤치용으로 지어낸 과제로 채점 / `--model` 외 omp 플래그 / 서브에이전트로 실행 / 셀 중 sandbox 수정
- 피험자의 "make verify 통과" 말 믿기 — 직접 돌린 게 채점
- 최선 실행만 보고, n=1 로 "신뢰 가능" 단정 / 산출물 수를 완성도로 읽기
- 실행 후 `sandbox/.git`·임시 DB 상태를 남기기(`--revert-only`)
