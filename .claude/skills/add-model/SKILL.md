---
name: add-model
description: oMLX 스택에 새 모델을 추가/등록할 때 쓴다 — 앱 스토어 다운로드(admin API), 레시피 등록, omp 배선, 라이브 반영·스모크까지 한 절차로. Ollama 롤백 경로는 부록.
---

# add-model (oMLX 시대, 2026-08-28 개정)

인자: HF repo(`mlx-community/<name>`), 역할(default / 대안 코더 / aux / advisor), MTP 드래프터 repo(있으면).

모델 저장소는 **oMLX 앱 스토어**(`~/.omlx/models`, 서빙 id는 짧은 형식 `<name>`)다. HF 캐시(`hf` CLI)는 2026-08-28 폐지 — 쓰지 않는다.

## 1. 다운로드 — oMLX admin API
```bash
curl -s -X POST http://127.0.0.1:9090/admin/api/hf/download \
  -H 'Content-Type: application/json' -d '{"repo_id":"mlx-community/<name>"}'
# 진행 확인: GET /admin/api/hf/models · 완료 후 ~/.omlx/models/mlx-community/<name>/ 실재 확인
```
드래프터도 같은 방식으로. 게이트 모델이면 `hf_token` 필드 추가. (앱 UI 다운로드와 같은 경로다.)

## 2. 레시피 — `omlx/model_settings.json`
키는 **짧은 id**(`<name>`). 코더는 `max_context_window 131072 / max_tokens 8192`, aux 는 `8192/1024`, 어드바이저는 `32768/4096`(48GB 캡). 샘플링은 모델 카드 권장값(출처 주석), `reasoning_parser: qwen` 필수, MTP 는 `vlm_mtp_enabled` + `vlm_mtp_draft_model: "<드래프터 짧은 id>"`. 3.8 계열은 `chat_template_kwargs: {"reasoning_effort": "medium"}`.

## 3. 프로파일 — `omlx/model_profiles.json` (필요 시)
`:mtp`/`:nothink` 별칭이 필요한 모델만(현재 35B 코더). 별칭은 **default 모델만 서빙에 노출**된다 — 실험 모델은 bare id 로 쓰고 프로파일은 만들지 않는다.

## 4. omp 배선 — `omp/models.yml` (+역할 변경 시 `config.fragment.yml`)
`providers.omlx.models` 에 `- id: "<짧은 id>"`(코더는 `api: openai-completions` — extraBody 경로), `contextWindow`/`maxTokens` 는 settings 와 동일. 기본 코더 교체면 `modelOverrides`(extraBody thinking_budget)와 `config.fragment.yml` `modelRoles` 도 — 그리고 CLAUDE.md "기본 코더" 줄과 함께 바꾼다(`make check-docs-sync`).

## 5. 문서 — README 모델 표 + `omlx/install.sh` 관리 주석
README 표에 행 추가(크기는 설치 후 `du -sh ~/.omlx/models/mlx-community/<name>`), install.sh 의 "앱 스토어 관리 대상" 주석에 짧은 id 명기(`make check-omlx-config` 가 이 명기를 요구한다).

## 6. 라이브 반영 + 스모크
```bash
cp omlx/model_settings.json ~/.omlx/model_settings.json
cp omlx/model_profiles.json ~/.omlx/model_profiles.json
cp omp/models.yml "$(omp config path | tail -1)/models.yml"
~/.omlx/bin/omlx restart
# 재시작 검증은 셔틀 메시지가 아니라 uptime 으로: lsof -nP -iTCP:9090 -sTCP:LISTEN -t | xargs ps -o etime=
curl -s http://127.0.0.1:9090/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"<짧은 id>","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":2000}'
```
think 모델 스모크는 `max_tokens` ≥1000(절단 시 reasoning 분리 오탐). MTP 는 서버 로그의 `vlm_mtp stats`(수락률)로 확인. 로드 크기를 README 에 실측 기록.

## 7. 검증·정리
`make check-omlx-config check-omp-models check-docs-sync` 초록 확인. 벤치 검증은 `/bench-model`(1단계) → 기본 코더 교체는 `/llm-bench`(2단계) 통과가 필요조건. 대체된 모델은 앱 UI 또는 `DELETE /admin/api/hf/models/<name>` 로 제거하고 문서 주석을 갱신한다.

## 부록 — Ollama 롤백 경로
Ollama 로 돌아갈 때만: `ollama/Modelfile.<name>`(num_ctx/num_predict), `ollama pull`+`create`, LaunchAgent. 상세는 git 이력의 이 파일 이전 판.
