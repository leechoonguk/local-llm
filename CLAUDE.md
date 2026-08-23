# local-llm — Claude 작업 규칙

Apple Silicon Mac에서 Ollama 로컬 LLM을 Hermes Agent / oh-my-pi(omp) 코딩 에이전트용으로 운영하는 설정 레포.
README.md 가 사람용 문서이자 실측 기록이다. 이 파일은 Claude가 작업할 때 지킬 규칙과, 코드에서 읽어낼 수 없는 환경 사실만 담는다.

## 환경 사실 (2026-08 기준)
- 주 호스트: Mac mini M4 Pro 64GB (`hw.model Mac16,11`). 48GB 맥에서도 재현 가능해야 한다.
- macOS GPU wired 한도 기본값은 RAM의 ~75%. 이걸 넘으면 Ollama가 레이어를 CPU로 내려 속도가 급락한다.
  `install.sh`가 RAM별로 `iogpu.wired_limit_mb`를 올린다(48GB→40960, 64GB→57344). sudo가 필요하다.
- 35B-A3B(qwen35moe) 실측: 로드 직후 23GB(nvfp4), 창이 차면 +~10GB. 창 크기는 로드 메모리를 바꾸지 않는다(64K/128K/256K 모두 23GB).
- nvfp4 태그는 Ollama의 MLX 경로(빠름, ~65 tok/s). HF GGUF(Q4/Q5)는 llama.cpp 경로(~42~49 tok/s). 모델 비교 시 포맷 차이를 속도 차이로 오해하지 말 것.
- 모델 구성의 단일 진실은 `omp/models.yml` + `omp/config.fragment.yml`. 라이브 사본은 `~/.omp/agent/` (`omp config path`).
- 기본 코더: `qwen3.6-coder` (창 131072 / 출력 8192 — README "컨텍스트 레시피" 실측). 보조: `qwen3.5-aux` (4B, thinking off).
- Ornith-1.5는 2026-08-23 검증 후 제외했다: 단발 벤치는 동률이었지만 장기 세션에서 느리고(3.5~4배) 분산이 컸다. 다시 제안하지 말 것.

## 규칙
1. **모델 검증은 단일 로드로.** 벤치/메모리 측정 전에 `ollama ps`의 다른 모델을 전부 `ollama stop`한다. `/bench-model` 스킬을 쓴다. 단발 벤치(`bench/`)는 필요조건일 뿐이다 — 기본 코더를 바꾸려면 실제 프로젝트의 장기 omp 세션(압축 횟수, 산출물, 게이트 통과, 소요 시간)으로 확인한다.
2. **벤치 수치는 자체 보고와 구분한다.** 개발사 벤치마크를 인용할 땐 "자체 측정"임을 명시하고, 우리 실측은 n과 조건(양자화, ctx, thinking, temp)을 함께 적는다.
3. **새 모델 추가는 `/add-model` 절차대로** 5곳을 한 번에 맞춘다: Modelfile, install.sh, models.yml, config.fragment.yml, README. 라이브 `~/.omp/agent/`도 동기화한다.
4. **Modelfile 파라미터**: `num_ctx`는 Modelfile로만 관리한다(`/v1` API는 요청에 실을 수 없음). omp `contextWindow`/`maxTokens`는 Modelfile `num_ctx`/`num_predict`와 같은 값이어야 한다(입력 상한 = num_ctx − num_predict). 샘플링은 모델 카드 권장값을 따르고 출처를 주석에 남긴다.
5. **models.yml 의 두 provider는 합치지 않는다.** `ollama`(openai-responses, thinking on)와 `ollama-nothink`(openai-completions + `reasoning_effort: none`)는 omp 스키마 제약 때문에 나뉜 것이다. 사유는 파일 상단 주석 참고.
6. **`brew services start ollama` 금지.** LaunchAgent(`com.ollama.serve`)만 쓴다.
7. **큰 다운로드(>10GB)와 sudo는 사용자가 직접.** pull 명령을 제시하고 기다린다. `install.sh` 실행도 sudo 프롬프트가 뜨므로 사용자에게 맡긴다.
8. **커밋/푸시는 요청 시에만.** 커밋 메시지는 영어, 본문에 실측 근거를 한 줄 남긴다.
9. **주석·README는 한국어**, 코드 식별자와 커밋 메시지는 영어. 기존 파일의 말투("~한다" 체)를 따른다.
10. 실측으로 얻은 숫자(메모리, tok/s, 중단 토큰 수)는 README의 해당 표에 날짜와 함께 기록한다. 추정치는 "추정"이라고 쓴다.

## 디렉터리
- `ollama/` — install.sh, Modelfile.*, LaunchAgent 템플릿
- `omp/` — models.yml(설치됨), config.fragment.yml(수동 병합)
- `bench/` — 코딩 모델 검증 하네스. `results/`는 gitignore
- `.claude/skills/` — bench-model, add-model
