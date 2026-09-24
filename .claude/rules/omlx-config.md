---
paths:
  - "omlx/**"
---

# oMLX 설정 (model_settings.json · model_profiles.json · install.sh)

`omlx/*.json` 은 `~/.omlx/` 로 복사되고 서버 재시작으로 반영된다. 값 하나가 MTP 를 조용히 끄거나 CoT 를 content 에 섞을 수 있어 기계 검사로 막는다 — `make check-omlx-config`.

## 숨김 항목
- `is_hidden: true` 만 담은 항목은 **서빙에서 빼기 위한 표시**다(드래프터·DFlash·대화 형식이 없는 베이스 판). 레시피를 요구하지 않는다. 앱이 `/v1/models` 에서 빼 주고, 그래야 omp discovery 목록이 실제로 쓸 수 있는 모델만 담는다. 파일에 직접 써 넣으면 앱이 무시하므로 `PUT /admin/api/models/<id>/settings` 로 적용한다(실측 2026-08-31).

## 설정 값(모델·프로파일 공통)
- `version: 1`. `max_context_window`, `max_tokens` 는 정수이고 `max_tokens < max_context_window`.
- **Qwen 계열**은 `enable_thinking: true` 면 `reasoning_parser: "qwen_3_5"` — oMLX 0.7.0.dev4 의 xgrammar 레지스트리가 인정하는 이름(`qwen_3_5`/`qwen_3`/`qwen_3_coder`)이어야 admin PUT 이 통과한다. 옛 `"qwen"` 은 2026-09-24 부로 미지 값(422). 사고 분리 자체는 0.7.0.dev4 에서 파서 없이도 되지만(네이티브 reasoning_content 경로), 이 값은 구조화 출력 문법 컴파일에 쓰이므로 유효한 이름을 둔다.
- 다른 계열은 파서 이름을 요구하지 않는다. 서버가 계열별 출력 파서를 스스로 붙이고(로그 `Output parser detected: <family>`), Gemma 4 는 xgrammar 0.2.3 이 `gemma_4` 구조 태그 등록을 주석 처리해 둬서(파라미터 문자열이 `"` 대신 `<|"|>`) 넣을 이름 자체가 없다 — 실측으로 `reasoning_content` 는 분리된다(2026-08-31).
- **MTP 를 죽이는 값 금지**: `repetition_penalty` 는 1, `presence_penalty` 는 0 만, `guided_grammar` 금지(비중립이면 BatchGenerator 폴백).
- `thinking_budget*` 도 MTP 를 끈다(레벨 무관, 2026-08-28 실측 75.8→63.7 tok/s) — 금지는 아니고 **의도된 트레이드오프**다(토큰 폭주 억제 우선). 켤 때는 `make smoke` 로 MTP 스킵을 확인하고 기록한다.
- `vlm_mtp_enabled: true` 면 `vlm_mtp_draft_model` 필수.
- `is_default: true` 는 정확히 1개. `active_profile_name` 은 실재하는 프로파일.

## 프로파일
- key == `name` == `api_name`. 노출 이름은 `<model>:<key>`.
- 같은 모델의 프로파일들은 `max_context_window`·`vlm_mtp_enabled`·`vlm_mtp_draft_model` 이 같아야 한다 — 엔진 시그니처가 같아야 리로드 없이 같은 슬롯을 쓴다(`:mtp` ↔ `:nothink`).
- `nothink` 는 `enable_thinking: false`, `mtp` 는 `vlm_mtp_enabled: true`.
- thinking 길이: Qwen3.8 은 `chat_template_kwargs.reasoning_effort`(`xhigh`/`medium`/`low`), Qwen3.6 은 템플릿이 무시하므로 budget 을 쓴다. **레벨별로 키 이름이 다르다(2026-08-28 확정)**: 모델 설정·프로파일 = `thinking_budget_enabled` + `thinking_budget_tokens`, 요청 = `thinking_budget`(omp `compat.extraBody`). 무효 키는 서버가 조용히 버린다 — 새 키는 `curl -s localhost:9090/openapi.json` 의 `ModelSettingsRequest` 로 실재를 확인하고, 적용은 `GET /admin/api/models` 로 되읽어 검증한다(`make smoke`).

## install.sh
- 모델과 드래프터마다 `$HF download mlx-community/<name>`(설정 키의 `--` 는 `/`) **또는** 앱 스토어 관리 주석에 짧은 이름 명기(2026-08-28 전면 포팅 — 모델은 oMLX 앱 다운로드 `~/.omlx/models` 관리).
- `memory_guard_tier` 를 `'safe'` 로 강제(이 레포의 `iogpu.wired_limit_mb` 티어와 일치), 포트 `9090`, 두 JSON 을 `cp … ~/.omlx/` 로 설치.
- 서버는 GUI 앱(`/Applications/oMLX.app`)이 관리한다. brew 서비스(`homebrew.mxcl.omlx`)와 예전 LaunchAgent(`com.local-llm.omlx`) 잔재는 걷어내고, `auto_start_on_launch` 를 False 로 쓴다(`autostart.md`). brew 포뮬러는 `hf` CLI 용으로만 남긴다.
- 실행은 사용자가 한다(대용량 다운로드).
