---
paths:
  - "omp/**"
---

# omp 모델 설정 (models.yml · config.fragment.yml)

`omp/models.yml` 은 `~/.omp/agent/models.yml` 로 그대로 설치되고, `config.fragment.yml` 은 `config.yml` 에 손으로 병합한다. 여기 값은 서빙 쪽(Modelfile, oMLX 설정)과 **같은 숫자**여야 한다 — `make check-omp-models`. 편집 후 `post-edit` 훅이 라이브 반영을 상기시킨다(자동 복사 없음).

## 두 Ollama provider 는 합치지 않는다
- `ollama`: `api: openai-responses`, thinking on. 코딩용.
- `ollama-nothink`: `api: openai-completions` + `compat.extraBody.reasoning_effort: none`. 제목·메모리·압축용.
- `api` 는 provider 수준 필드라 `modelOverrides` 로 못 바꾸고, `extraBody` 는 chat-completions 경로에만 실린다. 스키마 제약이지 취향이 아니다.

## Modelfile 과의 대응
- `ollama/Modelfile.<name>` 마다 `ollama-nothink.models` 에 `<name>:latest` — `contextWindow == num_ctx`, `maxTokens <= num_predict`(압축 요약은 더 짧아도 된다).
- `ollama.modelOverrides` 에 있는 `<name>:latest` 는 `contextWindow == num_ctx`, `maxTokens == num_predict`. discovery 캐시가 128000 폴백으로 되돌아간 적이 있어 창은 손으로 박는다.
- `<name>:latest` 를 쓰는 항목은 Modelfile 이 있어야 한다. `compactionModel` 은 omp 런타임에 없는 키라 2026-08-30 제거했다 — 압축은 현재 세션 모델·thinking 레벨로 수행된다.

## oMLX provider
- id 는 `<model>:<profile>`(`omlx/model_profiles.json` 의 `expose_as_model: true` 프로파일) 또는 `<model>`(`model_settings.json`). `contextWindow`/`maxTokens` 는 그쪽 `max_context_window`/`max_tokens` 와 같다.
- `compat.extraBody`(`thinking_budget` 등)를 싣는 id 는 `api: openai-completions` 여야 한다 — `openai-responses` 에선 extraBody 가 병합되지 않는다(실측 2026-08-24).

## config.fragment.yml
- `modelRoles.default`/`tiny` 는 models.yml 에 실재하는 `provider/id`. `defaultThinkingLevel` 명시.
- CLAUDE.md 의 "기본 코더"/"보조" 표기와 같아야 한다(`check-docs-sync`).
