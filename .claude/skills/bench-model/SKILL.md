---
name: bench-model
description: Ollama 코딩 모델 후보를 단일 로드로 실행 테스트 채점해 기존 코더와 비교한다. 새 모델/양자화를 평가하거나 "이 모델 써도 될까" 질문에 답할 때 사용.
---

# bench-model

후보 모델을 `bench/run.py`로 검증하고 `bench/report.py`로 표를 만든다. 인자: 모델 이름(들). 없으면 사용자에게 묻지 말고 `ollama list`에서 `*-coder*` 중 results가 없는 것을 고른다.

## 절차
1. 모델이 `ollama list`에 있는지 확인. 없으면 pull 명령만 제시하고 멈춘다(큰 다운로드는 사용자 몫).
   파생 모델이 필요하면 `/add-model`의 Modelfile 규칙대로 먼저 `ollama create`한다.
2. 기준선 필요 여부: `bench/results/<기본코더>/summary.json`이 없으면 기본 코더(CLAUDE.md 참고)도 같이 돌린다.
3. 실행 — 모델별로 순차, 백그라운드로:
   ```bash
   python3 bench/run.py <model> [--repeat 3]
   ```
   run.py가 다른 모델을 내리고 단일 로드한다. zsh에서 `=====` 같은 문자열을 echo하면 glob 오류가 나므로 구분선은 `-----`를 쓴다.
4. `python3 bench/report.py`로 표를 만들고 아래 기준으로 해석한다.
5. FAIL은 `bench/results/<model>/<t>/` 의 `sol.*`과 err를 열어 **명세 모호성인지 로직 버그인지** 구분한다. export 형태 같은 모호성이면 shim으로 재채점하고 결과에 병기한다.

## 해석 기준
- 정답률이 같으면 **합산 시간**(추론 토큰 양)이 에이전트 체감을 결정한다. tok/s는 포맷(nvfp4 MLX vs GGUF)에 좌우되므로 모델 품질 지표가 아니다.
- n=1 결과로 양자화 간 우열을 단정하지 않는다. 차이를 주장하려면 `--repeat 3`.
- `ollama ps`의 로드 크기는 로드 직후 값이다. 48GB 적합성은 +~10GB(65K 창 포화)를 더해 `iogpu.wired_limit_mb` 한도와 비교한다.
- 결과는 README "검증" 섹션 형식(날짜, RAM, 단일 로드, ctx, thinking, temp 명시)으로 보고한다.

## 과제 추가
`bench/tasks/tN_prompt.md` + `tN_test.{py,sh,js}`를 만들고 `run.py`의 `TASKS`에 (id, 코드블록 언어, 저장 파일명, 테스트 명령)을 추가한다. 프롬프트는 "Output ONLY the code in a single ```lang block"으로 끝내고, 테스트는 exit code로 판정한다. export/함수명 등 인터페이스는 프롬프트에 명시한다(모호하면 채점이 흔들린다).
