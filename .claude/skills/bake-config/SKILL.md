---
name: bake-config
description: 실측으로 확정한 로컬 LLM 구성을 라이브에 굽고 "정말 먹었는지"까지 검증할 때 쓴다 — 레포→라이브 동기화, 검증된 재시작, 스모크, make verify, 커밋. "설정을 반영해줘", "이 값이 안 먹는 것 같다", "지금 구성이 맞나" 에도 이 절차를 쓴다.
---

# bake-config — 확정 구성 굽기·검증

설정은 **레포가 단일 진실**이고 라이브(`~/.omlx/`, `~/.omp/agent/`)는 그 사본이다. 굽는 일은 복사가 아니라 **"서버가 그 값을 실제로 인정했는가"를 확인하는 일**이다 — 무효 키를 조용히 버리는 서버 앞에서 복사만으로는 아무것도 보장되지 않는다(2026-08-28 실측: `thinking_budget` 을 모델 설정에 넣어 두었으나 몇 주간 무시되고 있었다).

## 0. 전제
- **벤치 셀이 돌고 있지 않을 것** — `make bake` 가 `pgrep -f "omp -p"` 로 거부한다. 셀 중 설정을 바꾸면 그 셀의 스택이 모호해진다(실측 사고 1회).
- 레포가 커밋 가능한 상태. 하네스·설정 수정은 **즉시 커밋**한다 — 미커밋 수정은 sandbox 원복(`git checkout -- sandbox`)에 지워진다(실측 사고 2회).

## 1. 굽기
```bash
make bake     # 복사(omlx settings/profiles, omp models.yml) → 재시작 → make smoke → make verify
```
`make bake` 는 실패를 삼키지 않는다. 개별 단계가 필요하면:
```bash
cp omlx/model_settings.json ~/.omlx/model_settings.json
cp omlx/model_profiles.json ~/.omlx/model_profiles.json
cp omp/models.yml "$(omp config path | tail -1)/models.yml"
~/.omlx/bin/omlx restart
```
`config.yml` 은 **복사하지 않는다** — omp 자신이 쓰는 값(setupVersion, theme, 모델 셀렉터 저장값)이 함께 살기 때문에 `omp/config.fragment.yml` 의 키만 손으로 병합한다(`modelRoles`, `defaultThinkingLevel`, 선택적 `advisor`).

## 2. 재시작은 uptime 으로 검증한다
```bash
lsof -nP -iTCP:9090 -sTCP:LISTEN -t | xargs ps -o etime=
```
앱 셔틀은 **성공했는데도 `Failed to control oMLX.app` 을 뱉고, 실패했는데도 조용할 수 있다**(실측). 메시지가 아니라 uptime 이 진실이다. 재시작 없이도 oMLX 는 설정·모델을 핫 리로드하는 경우가 있다.

## 3. 검증 — `make smoke`
```bash
make smoke                      # 기본 코더
make smoke MODEL=<짧은 id>      # 특정 모델/프로파일
```
확인 항목: 서빙 목록·uptime·응답 길이·**reasoning 분리**·**MTP 발화**·**서버가 되읽어 준 설정값**. 규칙:
- think 모델 스모크는 `max_tokens >= 1000` — 절단되면 reasoning 이 분리 안 된 것처럼 보인다(오탐 실측).
- MTP 는 응답 본문에 흔적이 없다. **서버 로그의 `vlm_mtp stats`(수락률)** 로만 확인된다.
- 설정 적용 여부는 `GET /admin/api/models` 가 되읽어 주는 값으로 판정한다.

## 3b. 실전 실증 — 베이크 모드 셀(선택, 구성 변경이 클 때)
스모크는 요청 하나다. **구성이 에이전트 실행 경로 전체에서 먹는지**는 셀로 증명한다:
```bash
make preflight && BENCH_BAKED=1 node .claude/skills/llm-bench/runner.ts \
  --models omlx/<코더 짧은 id> --tasks rest --campaign baked --timeout 3000
```
`BENCH_BAKED=1` 은 오버레이·`--model`·`--smol`·어드바이저 주입을 전부 끄고 **라이브 설정만으로** omp 를 띄운다(모델은 `modelRoles.default` 가 정한다). 셀이 도는 동안 확인할 것:
- 서버 로그의 모델 분포 — 코더와 aux 만 나와야 한다(`grep -oE "model=[^ ,]+" ~/.omlx/logs/server.log | sort | uniq -c`)
- budget 적용의 지문 — `vlm_mtp routing skipped`(budget 을 쓰면 MTP 는 꺼진다)
- 주입 부재 — 새 오버레이 디렉터리 없음, `sandbox/WATCHDOG.yml` 없음, `__advisor*.jsonl` 없음
- 행 지표 — `baked: true`, `gate_runs`/`first_full_gate_s` 가 채워짐
실측 1회: 16개 항목(역할·창·budget 양쪽 레벨·드래프터·서버 정책·스토어·실제 호출 모델)이 전부 의도와 일치했다(`bench/2026-08-28.s2.baked.md`).

## 4. 값이 안 먹을 때 — 진단 순서
1. **키 이름을 스키마로 확인한다.** 레벨마다 이름이 다르다:
   - 요청 레벨: `thinking_budget` (omp `compat.extraBody`)
   - 모델 설정·프로파일 레벨: `thinking_budget_enabled` + `thinking_budget_tokens`
   ```bash
   curl -s localhost:9090/openapi.json | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)['components']['schemas']['ModelSettingsRequest']['properties']))"
   ```
   무효 키는 **에러 없이 버려진다** — 앱 UI 에 안 보이면 그 신호다.
2. **되읽어 확인**: `GET /admin/api/models` 의 해당 모델 `settings`.
3. **서버 로그를 읽는다**(`~/.omlx/logs/server.log`) — 폴백 사유가 문장으로 남는다(예: `vlm_mtp routing skipped ... request carries logits processors`).
4. 그래도 모르면 **한 번에 하나씩** 빼며 재시작-요청으로 이분 탐색한다(라이브만 임시 변경 → 끝나면 레포 값으로 원복).

## 5. 확정 구성(2026-08-28)
| 층 | 값 | 근거 |
|---|---|---|
| 코더 | `omlx/Qwen3.6-35B-A3B-5bit:mtp`, 창 131072/출력 8192 | MoE 활성 3B — 로컬 최속 손(9B 41-44, 4B+MTP 45.3 tok/s 대비) |
| thinking | 서버 `thinking_budget_enabled: true`+`_tokens: 2048`, omp `extraBody.thinking_budget: 2048`(이중 보장) | 스윕 실측(`bench/2026-08-28.s2.thinkbudget.md`): 5120 대비 2/2 초록·유일 scored green 38.6m, 1024 는 하한 초과 |
| aux(tiny) | `omlx/Qwen3.5-4B-4bit`(창 8192/출력 1024) + MTP 드래프터 | 4B 는 MTP 페어링으로 23.2→45.3 tok/s |
| compaction | `…:nothink` | 코더와 같은 엔진 슬롯 — 추가 상주 0 |
| 사고 강도 | `defaultThinkingLevel: medium` | `auto` 는 벤치 변동성의 원천이었다 |
| advisor | off(기본). 켜려면 `advisor.enabled: true` + `modelRoles.advisor: omlx/Qwen3.6-35B-A3B-5bit:nothink` | 헤드리스 실동 확인·조합은 기각(`bench/2026-08-28.s2.advmatrix.md`) |
| 모델 저장소 | oMLX 앱 스토어 `~/.omlx/models`, 짧은 서빙 id. 다운로드는 `POST /admin/api/hf/download` | HF 캐시 폐지(2026-08-28) — 절차는 `/add-model` |

## 6. 알려진 함정
- **`thinking_budget` 은 MTP 를 끈다 — 레벨 무관**(모델 설정·프로파일·요청 extraBody). 실측 2026-08-28: thinking ON + budget 없음 = MTP 발화 75.8 tok/s / budget 2048 = 스킵 63.7 tok/s. thinking 자체는 무관하다. 현행 구성은 **budget(토큰 폭주 억제)을 택하고 MTP 17% 를 포기**한 것 — 무제한 thinking 이 간단한 과제에 8351 토큰을 쓴 실측이 근거다. 로그 사유 = `positioned verify sampling is unavailable on VLMModelAdapter`.
  - 교훈: 프로파일 별칭으로 요청하면 **프로파일의 settings 가 적용된다** — base 모델 설정만 바꾸고 이분 탐색하다 1차 결론을 오판했다. 프로파일·base·요청 세 레벨을 모두 확인할 것.
- 비중립 `repetition_penalty`/`presence_penalty`, `guided_grammar` 는 MTP 를 죽인다 — 중립 유지.
- oMLX 는 `~/.omlx/settings.json` 에 auth secret 도 저장한다 — 커밋 금지, `install.sh` 가 필요한 키만 patch.
- `hot_cache_max_size` 는 RAM 티어별(64GB+ 8GB / 48GB 4GB) — 48GB 에서 8GB 를 쓰면 wired 한도(40GB)를 넘긴다.

## 7. 마무리
`make verify` 가 **실제 종료코드로** 초록이어야 한다 — `| tail`/`grep -q` 로 끝을 가리면 뒤쪽 검사 실패가 묻힌다(실측 사고 1회). 그런 다음 커밋: 메시지는 영어, 본문에 실측 근거 한 줄.
