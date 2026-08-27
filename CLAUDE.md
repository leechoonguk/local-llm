# local-llm — Claude 작업 규칙

Apple Silicon Mac에서 Ollama 로컬 LLM을 Hermes Agent / oh-my-pi(omp) 코딩 에이전트용으로 운영하는 설정 레포.
README.md 가 사람용 문서이자 실측 기록이다. 이 파일은 Claude가 작업할 때 지킬 규칙과, 코드에서 읽어낼 수 없는 환경 사실만 담는다.

## 환경 사실 (2026-08 기준)
- 주 호스트: Mac mini M4 Pro 64GB (`hw.model Mac16,11`). 48GB 맥에서도 재현 가능해야 한다.
- macOS GPU wired 한도 기본값은 RAM의 ~75%. 이걸 넘으면 Ollama가 레이어를 CPU로 내려 속도가 급락한다.
  `omlx/install.sh`가 RAM 티어별로 `iogpu.wired_limit_mb`를 올린다(48·64GB→RAM−8GB=40960/57344, 96GB+→RAM−12GB, 그 아래 유지) — 즉시 적용 + `/etc/sysctl.conf` 부팅 지속. sudo가 필요하다.
- 35B-A3B(qwen35moe) 실측: 로드 직후 23GB(nvfp4), 창이 차면 +~10GB. 창 크기는 로드 메모리를 바꾸지 않는다(64K/128K/256K 모두 23GB).
- nvfp4 태그는 Ollama의 MLX 경로(빠름, ~65 tok/s). HF GGUF(Q4/Q5)는 llama.cpp 경로(~42~49 tok/s). 모델 비교 시 포맷 차이를 속도 차이로 오해하지 말 것.
- 모델 구성의 단일 진실은 `omp/models.yml` + `omp/config.fragment.yml`(omp 쪽), `omlx/model_settings.json` + `omlx/model_profiles.json`(oMLX 쪽). 라이브 사본은 각각 `~/.omp/agent/` 와 `~/.omlx/`.
- 2026-08-24 부로 서빙을 oMLX(brew `jundot/omlx`, 포트 9090)로 전환했다(사용자 결정, 장기 세션 검증 전). 서버는 GUI 앱(`/Applications/oMLX.app`, DMG)이 관리하고 `omlx start|stop|restart`(앱 셔틀 `~/.omlx/bin/omlx`)로 제어한다 — brew services·LaunchAgent 아님(2026-08-25). jundot/omlx 탭·포뮬러는 2026-08-27 제거 — `hf` CLI 는 코어 포뮬러(`brew install hf`)로 대체. Ollama LaunchAgent 는 `launchctl disable` 상태로 남아 있다 — 롤백 절차는 README "oMLX 전환" 표.
- 기본 코더: `omlx/mlx-community--Qwen3.6-35B-A3B-5bit:mtp` (창 131072 / 출력 8192 — README "컨텍스트 레시피" 실측, MTP 드래프터 페어링). 보조: `omlx/mlx-community--Qwen3.5-4B-4bit` (thinking off).
- oMLX 에서 MTP 를 죽이는 설정: 비중립 `repetition_penalty`/`presence_penalty`, `guided_grammar`. 프로파일 수정 시 중립값 유지.
- oMLX thinking 분리에는 `reasoning_parser: qwen` 이 필수다(없으면 CoT 가 content 에 섞임). `--with-custom-kernel` 은 macOS 27 에서 brew 소스 빌드가 거부돼 실패한다(2026-08-24) — 표준 커널로 동작.
- README "Thinking 제어"의 "low/medium/high는 Qwen에서 효과 없음"은 **Ollama 한정**이다. oMLX는 토크나이저 chat template을 그대로 태우고, Qwen3.8 템플릿은 `reasoning_effort`(유효값 `xhigh`/`medium`/`low`, `high`/`none` 아님)를 네이티브로 해석한다 — 실측 전 재차 확인할 것. 3.8은 `medium`을 서버쪽 기본값(`chat_template_kwargs`)으로 고정했다(2026-08-24). **3.6의 chat template에는 이 로직이 없다** — `reasoning_effort`를 보내도 조용히 무시된다(에러 없음). 3.6에서 thinking 길이를 줄이려면 `thinking_budget_enabled`/`thinking_budget_tokens`(생성 시점 프로세서, 템플릿 무관)를 쓸 것.
- 3.8은 dense라 3.6(MoE, 활성 3B)보다 원천적으로 느리다 — 실측(2026-08-24, MTP on, 웜 디코드): 3.6 75~80 tok/s, 3.8 oQ6(6bit) 10.7 tok/s(~7.3배 느림), 3.8 nvfp4(4bit) 21.0 tok/s(~3.7배 느림, oQ6의 2배). nvfp4 쪽 수치는 2026-08-20 Ollama nvfp4 벤치(22~29 tok/s)와 같은 대역이라 oMLX 자체 결함이 아님을 교차 확인함. **2026-08-25 제거**: s2 벤치(`bench/2026-08-24.s2.qwen-recipe.md`)에서 oQ6·nvfp4 둘 다 writes 0(무산출)로 실패해 캐시·`omp/models.yml`·`omlx/*.json`·`install.sh`에서 걷어냈다. 위 속도 실측치는 왜 뺐는지의 근거로 남긴다.
- oMLX `memory_guard_tier` 는 `balanced` 대신 `safe` 로 강제한다(`omlx/install.sh`). `balanced`(RAM−6GB 정적 상한)가 이 레포의 `iogpu.wired_limit_mb` 티어보다 커서(64GB: 58GB > 56GB, 48GB: 42GB > 40GB) admin 대시보드가 계속 sysctl을 올리라는 배너를 띄운다 — 실사용 상한은 metal_cap이 커널 캡을 이미 접어 넣어 안전했지만(소스 확인), 커널 캡을 더 올리는 대신 oMLX 목표를 낮추는 쪽이 이식성 있다. `safe`(RAM−8GB)는 이 레포의 두 RAM 티어 모두에서 정확히 wired_limit_mb 값과 같아진다.
- Ornith-1.5는 2026-08-23 검증 후 제외했다: 단발 벤치는 동률이었지만 장기 세션에서 느리고(3.5~4배) 분산이 컸다. 다시 제안하지 말 것.
- omp **advisor 는 헤드리스(`-p`) 벤치에 부적합**하다. config(`advisor.enabled`) 경로는 무동작(4중 실측: 40분 셀·2턴·10턴·18.0.6 재프로브 모두 0건)이고, `--advisor` **CLI 플래그**는 런타임을 깨우지만 턴 리뷰 동안 도구 호출을 스킵시켜 루프를 교란한다(실측: 동일 과제 7요청/50초 → 25요청/4분, 'Skipped due to pending system advisory' 12건) — 벤치에는 영향 없고 인터랙티브 전용. 러너의 `BENCH_ADVISOR` 스위치는 재검증용으로 남긴다. 인터랙티브에서 켜려면 `advisor.model: omlx/…-5bit:nothink`(코더와 같은 엔진 슬롯이라 추가 상주 0)가 후보다.

## 규칙
1. **모델 검증은 단일 로드로.** 벤치/메모리 측정 전에 `ollama ps`의 다른 모델을 전부 `ollama stop`한다(oMLX 는 서버 재시작 후 로그 `total:` 확인). 단발 벤치(`/bench-model`, 1단계)는 필요조건일 뿐이다 — 기본 코더를 바꾸려면 `/llm-bench`(2단계, `sandbox/` 장기 omp 세션: 산출물, 게이트, 회귀, 소요 시간, n≥2)로 확인한다. 로컬 LLM 설정과 벤치는 이 워크스페이스에서만 관리한다 — fast-api-standard 에 벤치 자산을 다시 두지 말 것.
2. **벤치 수치는 자체 보고와 구분한다.** 개발사 벤치마크를 인용할 땐 "자체 측정"임을 명시하고, 우리 실측은 n과 조건(양자화, ctx, thinking, temp)을 함께 적는다.
3. **새 모델 추가는 `/add-model` 절차대로** 5곳을 한 번에 맞춘다: Modelfile, install.sh, models.yml, config.fragment.yml, README. 라이브 `~/.omp/agent/`도 동기화한다(`make check-live-sync` 가 어긋난 곳과 명령을 알려준다).
4. **Modelfile 파라미터**: `num_ctx`는 Modelfile로만 관리한다(`/v1` API는 요청에 실을 수 없음). omp `contextWindow`/`maxTokens`는 Modelfile `num_ctx`/`num_predict`와 같은 값이어야 한다(입력 상한 = num_ctx − num_predict). 샘플링은 모델 카드 권장값을 따르고 출처를 주석에 남긴다.
5. **models.yml 의 두 provider는 합치지 않는다.** `ollama`(openai-responses, thinking on)와 `ollama-nothink`(openai-completions + `reasoning_effort: none`)는 omp 스키마 제약 때문에 나뉜 것이다. 사유는 파일 상단 주석 참고.
6. **`brew services` 로 Ollama/oMLX 를 띄우지 않는다.** Ollama 는 레포 LaunchAgent(`com.ollama.serve`), oMLX 는 GUI 앱만 쓰고, 둘 다 자동 시작·자동 재시작(RunAtLoad/KeepAlive, 로그인 항목, oMLX `auto_start_on_launch`)은 꺼 둔다 — `make check-autostart`. 기동은 `launchctl kickstart -k`.
7. **sudo는 사용자가 직접.** sudo가 필요한 단계(예: `iogpu.wired_limit_mb`, `install.sh`의 sysctl)는 명령을 제시하고 기다린다. **모델 다운로드(`hf download`/`ollama pull`)는 에이전트가 직접 해도 된다**(2026-08-25 사용자 허용, `pre-bash` deny 제거). `install.sh` 전체 실행은 sudo를 포함하므로 여전히 사용자 몫이다.
8. **커밋/푸시는 요청 시에만.** omp 하네스는 훅으로 강제한다 — `sandbox/.omp/hooks/pre/strict-no-vcs-publish.ts` 가 피험자의 git commit/push 를 deny. Claude 쪽 ask 게이트는 승인 부담으로 2026-08-27 제거(행동 규칙으로만 유지). 커밋 메시지는 영어, 본문에 실측 근거를 한 줄 남긴다.
9. **주석·README는 한국어**, 코드 식별자와 커밋 메시지는 영어. 기존 파일의 말투("~한다" 체)를 따른다.
10. 실측으로 얻은 숫자(메모리, tok/s, 중단 토큰 수)는 README의 해당 표에 날짜와 함께 기록한다. 추정치는 "추정"이라고 쓴다.
11. **표준은 `.claude/rules/`, 검증은 `make verify`.** 대상 파일(bench/, ollama/, omlx/, omp/, 문서, 스킬, 하네스)마다 규칙 파일이 있고 같은 이름의 검사(`.claude/hooks/check-<name>.ts`)가 그것을 기계로 확인한다. 편집하면 `PostToolUse` 훅이 해당 검사를 돌려 위반을 돌려주고, 규칙 6·7 의 금지 명령은 `PreToolUse` 훅이 deny 한다. 작업을 마쳤다고 보고하기 전과 커밋 전에 `make verify` 가 초록이어야 한다. 규칙·검사·Makefile 타깃은 한 이름으로 넷을 같이 추가한다(`.claude/rules/harness.md`).

## 디렉터리
- `ollama/` — install.sh, Modelfile.*, LaunchAgent 템플릿
- `omp/` — models.yml(설치됨), config.fragment.yml(수동 병합)
- `bench/` — **결과만**, 플랫. `<date>.<s1|s2>.<subject>.md(+.json)` 캠페인 단위, 표준은 `bench/README.md`. 수행 환경은 여기 두지 않는다
- `sandbox/` — 2단계 벤치 피험자 트리(fast-api-standard 를 batch/user/integration 코어로 줄인 사본, 포트 18000/15173/15432/16379, compose 프로젝트 `local-llm-sandbox`). git 저장소 아님(local-llm 이 추적) — 마이그레이션은 git 없이 하네스를 통과하도록 정리했다. `sandbox/SANDBOX.md`
- `.claude/skills/llm-bench/` — 2단계 러너(`runner.ts`)·브리핑(`tasks/`)·Mode A 레퍼런스(`reference/`). 2026-08-24 에 fast-api-standard 에서 옮겨 왔고 그쪽에는 더 이상 없다
- `.claude/skills/` — bench-model(1단계), llm-bench(2단계), add-model
- `.claude/rules/` — 대상별 표준(paths 프런트매터). `.claude/hooks/` — 검사 `check-<name>.ts`·훅 진입점(`pre-bash`, `pre-write`, `post-edit`)·공용 `lib/`. `Makefile` — `verify`/`check-<name>`. 세부는 README "검증"
