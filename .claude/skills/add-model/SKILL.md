---
name: add-model
description: 이 레포에 Ollama 모델을 추가/교체한다 — Modelfile, install.sh, omp models.yml, config.fragment.yml, README, 라이브 ~/.omp/agent 를 한 번에 맞춘다. "모델 추가해줘", "기본 코더 바꿔줘"에 사용.
---

# add-model

인자: 베이스 모델(Ollama 태그 또는 `hf.co/<repo>:<quant>`), 파생 이름(`<family>-coder[-qN]` / `-aux`), 역할(default / 대안 / tiny).

## 1. 베이스 확인
- `ollama list`에 있는지. 없으면 pull 명령을 제시하고 기다린다(>10GB는 사용자가 직접).
- `ollama show <base>`로 아키텍처·양자화·컨텍스트·capabilities(tools/thinking)를 읽는다. tools 없으면 코더로 부적합.
- 모델 카드에서 권장 샘플링(temp/top_p/top_k)을 찾아 출처를 주석에 남긴다.

## 2. Modelfile — `ollama/Modelfile.<name>`
기존 `Modelfile.qwen3.6-coder`를 복사해 FROM과 헤더 주석만 바꾼다. 코더는 `num_ctx 65536 / num_predict 32768`, 보조는 `8192 / 1024`. `ollama create <name> -f ollama/Modelfile.<name>`.

## 3. install.sh
`# --- Models ---` 블록에 `ollama pull` + `ollama create` 추가. 선택 설치면 `--with-27b`처럼 플래그 분기. 기본 코더를 바꾸면 `REQUIRED=("default: ollama/<name>")`와 마지막 `echo "done. test: ..."`도 바꾼다.

## 4. omp/models.yml
- `providers.ollama.modelOverrides.<name>:latest` — `contextWindow`(= num_ctx), `maxTokens: 8192`(코더), `compactionModel: ollama-nothink/<name>:latest`.
- `providers.ollama-nothink.models`에 `- id: <name>:latest, contextWindow, maxTokens: 4096` 추가(압축 요약이 같은 로드 슬롯을 쓰게).
- 왜 이렇게 나뉘는지는 파일 상단 주석. 합치지 말 것.

## 5. omp/config.fragment.yml
역할이 default/tiny면 `modelRoles` 값 교체. 주석에 모델 크기·창·thinking 여부.

## 6. README
모델 표(크기는 `ollama list`), 설치 명령 주석, `modelRoles` 예시, 파일 목록. 검증을 했으면 `/bench-model` 결과를 "검증" 섹션에 날짜와 조건을 붙여 기록.

## 7. 라이브 적용 + 스모크
```bash
D=$(omp config path | tail -1)
cp omp/models.yml $D/models.yml
sed -i '' 's|^  default: ollama/.*|  default: ollama/<name>|' $D/config.yml   # 역할 바꿀 때만
curl -s http://127.0.0.1:11434/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"<name>:latest","messages":[{"role":"user","content":"Reply with exactly: OK"}],"reasoning_effort":"none","max_tokens":20}'
```
nothink 경로가 2~3 토큰으로 `OK`를 내면 정상. `ollama ps`로 로드 크기를 README에 기록.

## 8. 정리
대체된 파생 모델은 `ollama rm` + Modelfile 삭제(사용자에게 알림). 커밋은 요청 시에만.
