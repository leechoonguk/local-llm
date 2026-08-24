---
paths:
  - "omlx/**"
---

# oMLX 설정 (model_settings.json · model_profiles.json · install.sh)

`omlx/*.json` 은 `~/.omlx/` 로 복사되고 서버 재시작으로 반영된다. 값 하나가 MTP 를 조용히 끄거나 CoT 를 content 에 섞을 수 있어 기계 검사로 막는다 — `make check-omlx-config`.

## 설정 값(모델·프로파일 공통)
- `version: 1`. `max_context_window`, `max_tokens` 는 정수이고 `max_tokens < max_context_window`.
- `enable_thinking: true` 면 `reasoning_parser: "qwen"` 필수 — 없으면 thinking 이 content 에 섞인다.
- **MTP 를 죽이는 값 금지**: `repetition_penalty` 는 1, `presence_penalty` 는 0 만, `guided_grammar` 금지(비중립이면 BatchGenerator 폴백).
- `vlm_mtp_enabled: true` 면 `vlm_mtp_draft_model` 필수.
- `is_default: true` 는 정확히 1개. `active_profile_name` 은 실재하는 프로파일.

## 프로파일
- key == `name` == `api_name`. 노출 이름은 `<model>:<key>`.
- 같은 모델의 프로파일들은 `max_context_window`·`vlm_mtp_enabled`·`vlm_mtp_draft_model` 이 같아야 한다 — 엔진 시그니처가 같아야 리로드 없이 같은 슬롯을 쓴다(`:mtp` ↔ `:nothink`).
- `nothink` 는 `enable_thinking: false`, `mtp` 는 `vlm_mtp_enabled: true`.
- thinking 길이: Qwen3.8 은 `chat_template_kwargs.reasoning_effort`(`xhigh`/`medium`/`low`), Qwen3.6 은 템플릿이 무시하므로 `thinking_budget`(omp 쪽 extraBody).

## install.sh
- 모델과 드래프터마다 `$HF download mlx-community/<name>`(설정 키의 `--` 는 `/`).
- `memory_guard_tier` 를 `'safe'` 로 강제(이 레포의 `iogpu.wired_limit_mb` 티어와 일치), 포트 `9090`, 두 JSON 을 `cp … ~/.omlx/` 로 설치.
- brew 서비스(`homebrew.mxcl.omlx`)는 내리고 레포 LaunchAgent `com.local-llm.omlx`(RunAtLoad/KeepAlive false)로 바꾼다. `auto_start_on_launch` 를 False 로 쓴다(`autostart.md`).
- 실행은 사용자가 한다(대용량 다운로드).
