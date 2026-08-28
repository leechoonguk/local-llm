# Local LLM Setup — Apple Silicon (oMLX / Ollama)

Hermes Agent / oh-my-pi(omp) 용 로컬 LLM 서버 구성. Mac mini M4 Pro 64GB 기준이며, 48GB 맥에서도 동일하게 재현 가능하다.

**2026-08-24 부로 서빙을 oMLX 로 전환했다** — 아래 "oMLX 전환" 참고. Ollama 구성(ollama/, LaunchAgent)은 롤백용으로 그대로 둔다.

## 왜 Ollama인가 (2026-08-20 결정, 08-24 번복)

oMLX와 Ollama를 같은 모델(Qwen3.8-27B NVFP4)로 직접 벤치한 결과 Ollama로 선정했다. 2026-08-20 기준 둘 다 Apple Silicon에서 MLX 엔진을 쓰므로 엔진 차이는 없고, 실측 차이는 다음과 같았다.

| 항목 | oMLX (MTP 적용) | Ollama 0.32.14 |
|---|---|---|
| 15K 프롬프트 캐시 적중 시 TTFT | 11~17s (고정) | **0.2~0.6s** |
| 툴콜 생성 속도 | 19 tok/s | **23 tok/s** |
| `response_format: json_schema` | 12 tok/s (추측 디코딩 폴백) | **22.5 tok/s** (유지) |
| Hermes / omp 공식 통합 | LM Studio 호환 방식 우회 | 네이티브 (`ollama launch`) |
| 단점 | — | 프리픽스 캐시 미스가 간헐적 (같은 15K 프리픽스를 절반 재프리필, 80~90s) |

oMLX는 `thinking_budget_enabled`가 켜져 있으면 Qwen VLM 어댑터에서 MTP가 통째로 비활성화되는 함정이 있었다(기본 설정 상태에서는 MTP가 한 번도 동작하지 않았음).

## oMLX 전환 (2026-08-24)

사용자 결정으로 oMLX 0.6.3rc2 (`brew tap jundot/omlx`, `--with-custom-kernel`) 로 전환했다.
08-20 벤치 시점과 달라진 점 (소스 확인, omlx `model_settings.py`):

- **thinking_budget → MTP 비활성 함정이 수정됐다.** vlm_mtp 경로가 verify 시점에
  `ThinkingBudgetProcessor` 를 적용해(`MTPProcessingSampler`) 더 이상 BatchGenerator 로
  폴백하지 않는다. 남은 MTP 비활성 조건은 비중립 `repetition_penalty`/`presence_penalty` 와
  `guided_grammar` 뿐이다 — 우리 레시피는 중립값이라 안전.
- 계층 KV 캐시(RAM + SSD paged prefix cache)가 생겨 08-20 의 최대 약점이던
  "캐시 적중 시에도 TTFT 11~17s" 가 개선됐을 가능성이 있다 — **재실측 전까지는 추정**.

구성:

| 항목 | 값 |
|---|---|
| 서버 | GUI 앱 `/Applications/oMLX.app`(DMG, 2026-08-25) — 메뉴바 Start/Stop 또는 `omlx start|stop|restart`. brew services(KeepAlive)·LaunchAgent 는 쓰지 않는다(`make check-autostart`), 포트 9090 (8000 은 FastAPI 등 개발 서버와 충돌해 이전, 2026-08-24) |
| 코더 | `Qwen3.6-35B-A3B-5bit` (23GiB, oMLX 앱 스토어 `~/.omlx/models` — 2026-08-28 전면 포팅, HF 캐시 폐지) |
| MTP 드래프터 | `Qwen3.6-35B-A3B-MTP-5bit` (0.6GiB, `qwen3_5_mtp` 타입, 앱 스토어) |
| aux | `Qwen3.5-4B-4bit` (2.9GiB, thinking off, 앱 스토어) + MTP 드래프터 `Qwen3.5-4B-MTP-4bit` (83MiB, 45.3 tok/s 실측 2026-08-28) |
| ~~실험 9B 코더·3.8 어드바이저~~ | 2026-08-28 어드바이저 매트릭스 기각과 함께 **삭제**(`bench/2026-08-28.s2.advmatrix.md` — MoE 속도 역전·실행 불능). aux 는 MTP 드래프터 페어링(45.3 tok/s 실측) 유지 |
| ~~무거운 추론~~ | ~~`Qwen3.8-27B-oQ6`/`nvfp4`~~ — **2026-08-25 제거**(s2 벤치 writes 0 실패, `bench/2026-08-24.s2.qwen-recipe.md`). 아래 3.8 실측 절은 근거로 보존 |

**3.8 thinking effort는 `medium`으로 고정한다 (2026-08-24).** 아래 "Thinking 제어" 절의
"low/medium/high는 Qwen에서 효과 없음"은 **Ollama 한정 결론**이었다 — oMLX는 토크나이저의
실제 chat template(`chat_template.jinja`)을 그대로 태우는데, Qwen3.8 템플릿이 `reasoning_effort`
를 네이티브로 해석한다: 유효값은 `xhigh`(기본) / `medium` / `low` 뿐이고(`high`/`none`이 아니다),
`xhigh`/`low`는 지시문을 프롬프트에 주입하고 `medium`은 지시문 없이 모델 기본 판단에 맡긴다.
`omlx/model_settings.json` + `model_profiles.json`(`:mtp`/`:nothink` 둘 다)의
`chat_template_kwargs: {"reasoning_effort": "medium"}` 으로 서버쪽 기본값을 박았다 —
클라이언트가 값을 안 보내도 적용되고, 요청에서 명시하면 오버라이드 가능(강제 아님).

실측 (2026-08-24, 재시작 후, `Qwen3.8-27B-oQ6:mtp`, 동일 프롬프트 "BST 노드 삭제(자식 둘)" 설명, n=1/레벨):

| `reasoning_effort` | reasoning_content 길이(문자) | completion 토큰 | 소요 시간 |
|---|---|---|---|
| `low` | 629 | 1632 | 164.7s |
| `medium` (서버 기본값) | 645 | 1155 | 114.8s |
| `xhigh` (템플릿 기본값) | 335 | 1565 | 156.7s |

메커니즘 자체는 동작한다 — 레벨별로 reasoning_content 문구가 실제로 달라진다(`xhigh`는 "inorder successor/predecessor" 구조를 명시적으로 더 설계하고 들어감, `low`/`medium`은 더 즉흥적). 다만 길이가 레벨과 단조 관계가 아니다(`xhigh`가 가장 짧음) — **n=1, temp 0.6 샘플링 노이즈일 가능성이 높다.** 레벨 간 실제 차이를 확정하려면 반복 실측(n≥3)이 필요하다. 27B dense라 요청당 114~165s로 느리다 — README "선정 근거" 표의 27B prefill 느림 특성과 일치.

**3.6은 `reasoning_effort`가 통째로 no-op이다 (2026-08-24, 실측 정정).** 3.8과 같은 조작을
3.6(`Qwen3.6-35B-A3B-5bit:mtp`)에 해보면 아무 일도 없다 — seed 고정, 나머지 파라미터 동일,
`/v1/chat/completions`의 `reasoning_effort`와 `/v1/responses`의 `reasoning.effort` 둘 다:

| `reasoning_effort`/`reasoning.effort` | completion/output 토큰 | reasoning 토큰 |
|---|---|---|
| `low` | 8351 | 7659 |
| `high` | **8351 (완전히 동일)** | **7659 (완전히 동일)** |

seed로 다른 변수를 다 죽였는데 값이 바이트 단위로 같으면 그 파라미터가 무시된 것이다.
3.8의 chat template은 `reasoning_effort`를 네이티브로 해석하지만(위 절), **3.6의 template은
그 필드를 아예 안 읽는다** — 모델 버전마다 template 능력이 다르다는 뜻이지, oMLX 서버의
결함이 아니다. `chat_template_kwargs`에 넣어도 top-level에 넣어도 동일하게 무효라, 3.6
프로파일에 `reasoning_effort: medium`을 박는 조치는 **효과가 없다** — 시도했다가 철회했다.

**3.6에서 진짜 먹는 건 `thinking_budget`이다 (같은 실측).** 이건 template이 아니라 서버가
직접 강제하는 토큰 상한이다:

| `thinking_budget` | completion 토큰 | 소요 시간 |
|---|---|---|
| 64 | 491 | 14s |
| 3000 | 2901 | 73s |

64→3000 (47배)에 토큰도 시간도 거의 비례해서(6배/5배) 반응한다. 그리고 상한을 아예
안 걸면(위 표의 `low`/`high` 둘 다, 실질적으로 미지정과 동일) 간단한 산수 문제에도
**8351 토큰**을 쓴다 — 즉 지금 3.6은 이미 사실상 무제한으로 생각하고 있었고, REST 벤치
셀이 45분 안에 자기 회귀(`env.py`)를 못 고친 게 "effort 부족"이 아니라 **"생각을 안
멈춰서 턴이 안 돌았을 가능성"**을 가리킨다 — 재벤치 전까지는 가설.

**`compat.extraBody`는 omp `api: openai-responses` 요청에 안 실린다 (2026-08-24, 실측).**
`thinking_budget`을 3.6 mtp의 `modelOverrides.compat.extraBody`에 넣고 daemon broker를
두 번(재시작 전/후) 갈아치우며 `omlx.log` trace로 실제 wire 바디를 봤는데 두 번 다
빠져 있었다 - 캐싱이 아니라 `openai-responses` 코드 경로 자체가 `extraBody`를 병합하지
않는다. 그 모델 항목에만 `api: openai-completions`(`/v1/chat/completions`)를 오버라이드
하니 즉시 실렸다(trace 확인: `"thinking_budget":5120`). `omp/models.yml`의 3.6 `:mtp`
항목만 이렇게 바꿨다 - `:nothink`/3.8은 `openai-responses`로 남겨 사고 범위를 좁혔다.

**SSD/hot 캐시 (2026-08-24, 정정).** 앞서 "SSD prefix cache가 꺼져 있다"고 결론 냈는데
**틀렸다** — `~/.omlx/settings.json`의 `cache.ssd_cache_dir: null`은 "꺼짐"이 아니라
"기본 경로(`~/.omlx/cache`) 사용"이다. 서버 로그(`PagedSSDCacheManager initialized`)로
확인하면 오늘 세션 내내 이미 켜져 있었다(157파일, 15.55GB 누적). 실제로 꺼져 있던 건
`cache.hot_cache_max_size`(기본값 `"0"`) — SSD 캐시 앞단의 인메모리 레이어가 없었다.
`install.sh`에 `hot_cache_max_size: "4GB"` patch를 추가했다(재시작 로그로 확인:
`hot_cache=4.00 GB`). `ssd_cache_dir`는 명시하지 않는다 — 명시했다가 오타 하나로 경로가
갈리면 이미 데워진 캐시가 고아가 된다(이 세션에서 실제로 15.55GB를 날릴 뻔했다); 기본
경로를 신뢰하는 쪽이 안전하다.

**3.8 양자화별 속도 비교 (2026-08-24, 동일 프롬프트, MTP on, `reasoning_effort: medium`, 웜 디코드 — 로드 시간 제외):**

| | 3.6 (35B-A3B MoE, 5bit) | 3.8 oQ6 (dense, 6bit) | 3.8 nvfp4 (dense, 4bit) |
|---|---|---|---|
| 웜 디코드 속도 | 75~80 tok/s (MTP 발화 시. **2026-08-28 현재 35B 는 thinking on 이면 MTP 가 스킵돼 62~65 tok/s** — CLAUDE.md 환경 사실 참고) | 10.7 tok/s | **21.0 tok/s** |
| 3.6 대비 배수 | 1x | ~7.3배 느림 | ~3.7배 느림 |

nvfp4가 oQ6보다 **약 2배 빠르다** — 6bit이 4bit보다 가중치당 연산/대역폭이 더 들어가는 게 dense 모델에서 그대로 드러난다(MoE인 3.6은 활성 파라미터가 3B뿐이라 이 효과가 훨씬 작다). 이 nvfp4 수치(21.0 tok/s)는 2026-08-20 Ollama 시절 벤치(22~29 tok/s, 같은 nvfp4)와도 같은 대역이라 oMLX 자체가 3.8을 유난히 느리게 만드는 건 아니라는 교차 확인이 된다 — **느림의 원인은 dense 27B 아키텍처 자체**(토큰당 27B 전부 활성, MoE 3.6은 3B)이고, oQ6는 거기에 양자화 비용까지 얹힌 것.

`mlx-community--Qwen3.8-27B-nvfp4:mtp`/`:nothink`도 oQ6와 같은 패턴으로 등록했었으나, **2026-08-25 oQ6와 함께 제거**했다 — s2 벤치(`bench/2026-08-24.s2.qwen-recipe.md`)에서 dense 27B(oQ6·nvfp4)가 두 과제 모두 writes 0(무산출)으로 실패했다. 위 속도 실측치는 근거로 남긴다.
| 프로파일 | `:mtp` = coder 레시피(131072/8192, temp 0.6/top_p 0.95/top_k 20/min_p 0) + MTP on + `thinking_budget` 5120(서버 기본값, 2026-08-24 REST 캠페인에서 무제한 대비 회귀 0 — `bench/2026-08-24.s2.omlx.md`; omp `extraBody` 와 같은 값) / `:nothink` = 동일 + thinking off(압축용) |
| 설정 파일 | `omlx/model_settings.json`, `omlx/model_profiles.json` → `~/.omlx/` 로 설치 (`omlx/install.sh`). 전역 `~/.omlx/settings.json` 은 auth secret 이 있어 커밋하지 않는다 |
| Ollama | `launchctl bootout` + `disable` (로그인 자동 시작 꺼짐). 복귀: `launchctl enable gui/$UID/com.ollama.serve && launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.ollama.serve.plist && launchctl kickstart gui/$UID/com.ollama.serve` (템플릿이 RunAtLoad false 라 bootstrap 만으로는 뜨지 않는다) |
| `memory_guard_tier` | `safe` (8GB 정적 예약, `omlx/install.sh`). 기본 `balanced`(6GB 예약)의 정적 상한이 이 레포 wired_limit_mb 보다 커서(64GB: 58GB > 56GB) admin 대시보드가 sysctl을 더 올리라고 경고했다 — 실사용 상한은 metal_cap이 커널 캡을 접어 넣어 항상 안전했지만(소스 확인, 2026-08-24), 커널 캡을 더 올리기보다 oMLX 목표를 캡 아래로 낮추는 쪽이 48GB로 옮겨도 깨지지 않는다. `safe`의 RAM−8GB 은 이 레포의 두 RAM 티어 모두에서 정확히 wired_limit_mb 값과 같다 |

초기 실측 (2026-08-24, M4 Pro 64GB, wired 57344MB, 단발 스모크 — 짧은 프롬프트, MTP on, thinking on):

| 항목 | 값 |
|---|---|
| 코더 로드 (23.1GiB 5bit) | 3.4~3.9s (MLX lazy load) |
| 생성 속도 (n=2, 512~666 tok, 프리필 포함) | 75~80 tok/s — Ollama nvfp4 실측 ~65 tok/s 대비 빠르지만 **양자화가 달라(5bit vs nvfp4) 서버 차이로 단정하지 말 것** |
| `:nothink` 전환 | 리로드 없음, 같은 슬롯 (0.65s 응답) |
| aux(4B) 로드 후 코더 재호출 | 리로드 없음 — 동시 상주 확인 |
| thinking 분리 | `reasoning_parser: qwen` 필요. 없으면 CoT 가 content 에 섞인다. `/v1/responses` 는 reasoning/message 아이템으로 분리 |
| omlx-server RSS | 14.0GB (코더+aux 상주, mmap lazy 라 Ollama 의 23GB 상주 수치와 직접 비교 불가) |
| `--with-custom-kernel` | **빌드 실패** (macOS 27 은 brew Tier 1 이 아니라 소스 빌드 거부) — 표준 MLX 커널로 동작 중 |

미검증: 규칙대로 기본 코더 전환은 장기 omp 세션 실측이 필요조건이다. 이 전환은 그 검증
**이전**의 사용자 결정이며, 08-20 벤치의 TTFT/툴콜 수치(캐시 적중 TTFT 11~17s, json_schema
폴백)가 0.6.3rc2 의 SSD prefix cache 에서 뒤집혔는지 재실측할 것.

## 모델

| 모델 | 베이스 | 크기 | 용도 |
|---|---|---|---|
| `qwen3.6-coder` | `qwen3.6:35b-a3b-nvfp4` (MoE 35B, 활성 3B, 4bit) | 23GB | **주력**. 코딩/에이전트. 창 131072 / 출력 8192 |
| `qwen3.8-coder` | `qwen3.8:27b-nvfp4` (dense 27B, 4bit) | 18GB | 무거운 추론. prefill 느림 |
| `qwen3.5-aux` | `qwen3.5:4b-nvfp4` (dense 4B, 4bit) | 4GB | 보조 작업(제목/메모리/분류). 코더와 동시 상주 |

### 컨텍스트 레시피 (2026-08-23, fast-api-standard 장기 세션 실측)

실제 통합 과제(외부 API 1건: 마이그레이션·시드·`.http`·계약 픽스처 4개 산출, `make verify` 게이트)를 같은 브리핑·같은 하네스로 돌려 창 크기를 정했다. 모델당 1회.

| | qwen 64K | qwen 66K | qwen 128K | qwen 256K |
|---|---|---|---|---|
| 압축 | — | 1회 | **0회** | 0회 |
| 결과 | 88%에서 7턴 만에 정지 | 컬럼 3개 발명, 게이트 실패 | **4/4, 게이트 통과** | 4/4 (창의 27%만 사용) |
| 시간 | — | — | 10분 | 18분 |

- 과제의 토큰 수요는 58K~128K. 64K/66K는 담지 못하고, 128K부터는 모든 실행이 압축 0회였다. 레시피의 임무는 "수요를 압축 없이 담기".
- 256K는 추가 이득이 없다. 메모리는 동일(23GB)하고 시간만 1.8배.
- 출력 예약은 모델마다 다르다. qwen은 8K로 충분했다.
- 그래서 `num_ctx 131072 / num_predict 8192`, omp `contextWindow 131072 / maxTokens 8192`.

**Ornith-1.5-35B-A3B는 채택하지 않았다.** 단발 코딩 과제(`bench/`)에서는 qwen과 정답률 동률(3/4)에 추론 토큰이 훨씬 짧아 유망해 보였지만, 장기 세션에서 66K로는 압축 5회 끝에 산출물 0/4, 128K는 4/4이되 40분(qwen의 3.5~4배), 256K 재실행은 0/4로 분산이 컸고 출력 예약 33K가 필요했다. 단발 벤치는 필요조건일 뿐 에이전트 적합성은 보장하지 않는다 — 이 교훈이 `bench-model` 스킬에 적혀 있다.

### 모델·서빙 매트릭스 (2026-08-24, fast-api-standard 장기 세션 실측)

M4 Pro 64GB, 단일 로드, 창 131072 / 출력 8192, temp 는 각 모델 카드 권장값. thinking은
Ollama 세 모델은 `medium` 고정(Modelfile), oMLX `Qwen3.6-35B-A3B-5bit:mtp`는 **`medium`이
아니라 무제한** — 아래 "3.6은 `reasoning_effort`가 통째로 no-op이다" 절 참고, 이 표를
처음 채울 때는 몰랐던 사실이라 여기 정정해 둔다. 셀당 45분 상한. `fast-api-standard` 의
`make bench-llm`
(`skill://llm-bench` 2단계 러너)로 실행했고, 셀마다 트리를 세팅→실행→게이트 채점→원복한다.
과제는 두 가지다:

- **integration** — 실제 landed 커밋(외부 API I2570)의 재현. 산출물 6개(시드 2, `.http`, 픽스처, 테스트 배선 2)
- **REST** — `notice` CRUD 도메인 신규 작성. 산출물 13개(5계층, 배선, 마이그레이션, `.http`, 테스트 3)

| 서빙 / 모델 | integration | REST |
|---|---|---|
| Ollama `qwen3.6-coder` (35B-A3B nvfp4) | **6/6, 게이트 통과, 19분** | 5/13, FAIL 5, 32분 |
| Ollama `qwen3-coder` (30B-A3B Q4_K_M, instruct) | 4/6, FAIL 3, 13분 | **12/13, FAIL 1, 18분** |
| Ollama `qwen3.8-coder` (27.8B dense nvfp4) | 0/6, 45분 타임아웃 | 0/13, 45분 타임아웃 |
| **oMLX `Qwen3.6-35B-A3B-5bit:mtp`** (thinking 무제한) | **6/6, 게이트 통과, 16분 40초** | 15/13, FAIL 1(`env.py` `User` 등록 삭제 회귀), **45분 타임아웃** |
| oMLX `Qwen3.6-35B-A3B-5bit:mtp` + `thinking_budget 5120` | 미측정 | 15/13, FAIL 1(미완성 1, **회귀 0**), 43분 52초 자체 종료 |
| oMLX `Qwen3.8-27B-nvfp4:mtp` + `thinking_budget 2560` | 미측정 | 0/13, 45분 타임아웃 (read 39 / write 0) |

셀별 상세는 `bench/`(캠페인별 기록: `2026-08-23.s2.ollama-manual.md`, `2026-08-24.s2.ollama-matrix.md`,
`2026-08-24.s2.omlx.md`), 러너 원본 행은 `bench/2026-08-24.s2.llm-bench-runner.json`. 기록 표준은 `bench/README.md`.
이 표까지는 fast-api-standard 안에서 돌렸고, 08-24 부로 러너·브리핑을 `.claude/skills/llm-bench/` 로, 피험자 트리를
`sandbox/` 로 옮겼다 — 다음 캠페인부터는 `/llm-bench` 로 여기서 돈다.

- **oMLX 전환은 손해가 아니었다.** 같은 모델·같은 창으로 Ollama nvfp4 의
  19분 대비 16분 40초, 완주 여부는 동일. 위 "oMLX 전환" 절이 남긴 미검증 항목의 답이다.
  단 thinking 조건이 다르다(Ollama `medium` / oMLX 무제한) — 동일 조건 재측정 전이다.
  08-20 벤치의 TTFT 우려(캐시 적중 11~17s)는 55턴짜리 세션 총합에서 MTP 이득에 상쇄된
  것으로 보인다(추정 — TTFT 를 턴 단위로 따로 재지는 않았다).
- **`qwen3.8-coder`(dense)는 제외한다.** Ollama 에서 auto / medium / nothink / 45분 완주
  대기 ×2 / 루프 감지 종료(08-24 13:38, 2분 11초)까지 6회, oMLX nvfp4 `thinking_budget 2560`
  으로 1회 — **7회 전부 write 0**. 창을 32K→131K 로 고친 뒤에도 같다. oMLX 셀은 19턴/42툴콜
  동안 read 39·glob 2·grep 1 만 하고 탐색에서 실행으로 못 넘어갔다(thinking 은 정상 종료됐으니
  "생각만 하다 멈춤"이 아니다). MoE 두 개는 모두 산출했고 유일한 dense 만 실패했다.
  oQ6(6bit)만 미측정이다.
- **`thinking_budget` 은 회귀를 줄이는 방향이다.** 3.6 REST 무제한 실행은 `User` 등록을 지우고
  45분 내 못 고쳤는데, 5120 상한은 같은 15/13 을 회귀 0 으로 만들고 스스로 멈췄다(2632s).
  게이트 결과(FAIL 1)는 같으니 완주는 아니다. n=1.
- **모델이 과제별로 상보적이다.** 한 모델이 둘 다 잘하지 않는다. 정밀한 규약 준수가
  필요한 integration 은 thinking 모델이, 정형 5계층을 넓게 찍어내는 REST 는 instruct
  코더가 앞섰다. 셀당 n=1 이라 인과는 아직 가설이다.
- **산출물 수를 완성도로 읽으면 안 된다.** oMLX REST 실행은 45분 타임아웃까지 15/13 을
  만들었지만, 그 안에는 `alembic/env.py` 의 `User` 모델 등록 **삭제**(추가가 아니라 치환)가
  섞여 있었다. 그 상태로 `make migrate-gen` 을 돌렸다면 autogenerate 가 `remove_table user`
  를 제안한다 — 계정 테이블이 통째로 날아간다. 게이트가 즉시 잡았고, 모델은 45분 내내
  그 한 줄을 복구하지 못한 채 타임아웃됐다. `qwen3-coder`(instruct, Ollama)는 같은 REST
  과제를 18분·FAIL 1 로 마쳤으니, 이 실패는 REST 자체의 난도가 아니라 **이 조합
  (oMLX 서빙 + Qwen3.6 thinking)** 에 걸린 것으로 보인다`[INFERENCE]` — 셀당 n=1이라
  확정할 수 없다.
  **게이트 없이 이 등급의 로컬 모델을 쓰면 안 되는 이유가 이 한 줄이다.**

### 선정 근거 (M4 Pro 실측)

| | qwen3.6 35B-A3B nvfp4 | qwen3.6 35B-A3B mxfp8 | qwen3.8 27B nvfp4 |
|---|---|---|---|
| 생성 속도 (15K ctx) | **57 tok/s** | 25 tok/s | 22 tok/s |
| 생성 속도 (짧은 프롬프트) | **71 tok/s** | 43 tok/s | 29 tok/s |
| 15K 콜드 prefill | **~650 tok/s** | ~650 tok/s | ~90 tok/s (≈3분) |
| 32K ctx 상주 메모리 | ~30GB | ~45GB | ~25GB |

- MoE라도 8bit(mxfp8)은 대역폭에 묶여 4bit의 절반 속도 → nvfp4 채택, mxfp8 삭제.
- GGUF(q4_K_M/q8_0) 태그는 llama.cpp 경로라 MLX 추측 디코딩을 못 탄다. 반드시 MLX 태그(nvfp4/mxfp8)를 쓸 것.
- 27B dense는 같은 기기에서 prefill이 7배 느려 긴 컨텍스트 첫 턴에 수 분 걸린다.

### 파라미터 (Modelfile)

[Qwen 공식 모델 카드](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)의 "정밀 코딩(thinking)" 권장값을 적용했다.

| 파라미터 | 값 | 비고 |
|---|---|---|
| `temperature` | 0.6 | 일반 대화용 기본값은 1.0 |
| `top_p` / `top_k` / `min_p` | 0.95 / 20 / 0 | |
| `presence_penalty` | 0 | 코딩 권장. Ollama 기본 매니페스트는 1.5 |
| `num_ctx` | 131072 (3.6) / 32768 (3.8) / 8192 (aux) | Ollama 기본 4096은 에이전트용으로 불가. 3.6은 아래 "컨텍스트 레시피" 실측으로 정했다 |
| `num_predict` | 8192 (3.6) / 32768 (3.8) | **thinking 토큰을 포함**한다. 3.6은 장기 세션에서 8K로 충분했고, 창의 절반(32K)을 예약하면 입력 상한이 32.7K로 줄어 긴 턴이 거부된다 |

## Thinking 제어

Qwen3.6/3.8은 기본 thinking ON. 실측(qwen3.6 nvfp4, 단순 코딩 질문):

| 설정 | 생성 토큰 | 시간 |
|---|---|---|
| thinking off | 346 | 8s |
| thinking on | 2,240 | 33s |

- 끄기: `/api/chat`은 `"think": false`, `/v1/chat/completions`는 `"reasoning_effort": "none"`.
- `low/medium/high` 레벨은 Qwen에서 **효과 없음**(seed 노이즈 수준). on/off로만 제어할 것.
- 토큰 단위 thinking 예산 기능은 Ollama에 없다. 상한은 `num_predict`뿐이며 thinking+답변 합산이다.
- `/v1` 응답에서 thinking은 `message.reasoning` 필드로 온다.

## 서버 (LaunchAgent)

`com.ollama.serve.plist.template` → `~/Library/LaunchAgents/com.ollama.serve.plist`. **자동 시작·자동 재시작은 꺼져 있다**(`RunAtLoad`/`KeepAlive` false, 2026-08-24 — oMLX 와 동일 정책, `make check-autostart`). plist 는 환경변수와 로그 경로를 위한 것이고, 띄우는 것은 `launchctl kickstart -k gui/$(id -u)/com.ollama.serve` 뿐이다.

| 환경변수 | 값 | 이유 |
|---|---|---|
| `OLLAMA_HOST` | 127.0.0.1:11434 | |
| `OLLAMA_KEEP_ALIVE` | 1h | 기본 5분이면 대화 사이에 모델이 내려가 매번 5~11초 재로드 |
| `OLLAMA_NUM_PARALLEL` | 1 | 슬롯당 KV가 잡히므로 2→1로 64K ctx 기준 ~5GB 절약. 보조 요청은 thinking off라 직렬화돼도 0.4~1s |
| `OLLAMA_MAX_LOADED_MODELS` | 2 (64GB+) / 1 (그 아래) | 코더 + 보조 모델 동시 상주. `install.sh`가 RAM을 보고 채운다 — 1이면 보조 호출마다 코더가 내려간다(왕복 5~10s). 27B는 여전히 쓸 때만 스왑 |
| `iogpu.wired_limit_mb` (sysctl) | 48GB→40960, 64GB→57344, 96GB+→RAM−12GB, 그 아래 0(기본) | env가 아니라 macOS 커널 한도. 기본값(RAM의 ~75%)을 넘는 모델은 레이어가 CPU로 내려가 속도가 급락한다. `omlx/install.sh`(및 롤백용 `ollama/install.sh`)가 RAM 티어를 보고 즉시 적용 + `/etc/sysctl.conf`로 영구화(sudo, 거부 시 수동 명령 안내). |

컨텍스트 길이는 env(`OLLAMA_CONTEXT_LENGTH`)가 아니라 Modelfile `num_ctx`로 관리한다. `/v1` OpenAI 호환 API는 `num_ctx`를 요청에 실을 수 없기 때문이다.

로그: `~/Library/Logs/ollama/ollama.log` — `speculative decode stats` 라인으로 MTP 동작 확인 가능.

## 설치 / 재현

```bash
git clone https://github.com/leechoonguk/local-llm.git && cd local-llm
./ollama/install.sh              # qwen3.6-coder 만
./ollama/install.sh --with-27b   # qwen3.8-coder 까지
```

`install.sh`가 하는 일(재실행 안전):

1. **호스트 검사** — arm64 macOS가 아니면 즉시 중단한다(MLX 태그는 Apple Silicon 전용. 안 막으면 수십 GB를 내려받고 나서 실패한다). RAM으로 두 가지를 정한다: `OLLAMA_MAX_LOADED_MODELS`(64GB 이상 2, 그 아래 1)와 **보조 모델 설치 여부**. 슬롯이 하나면 보조 호출마다 코더가 왕복 5~10s 스왑하므로 손해다 — 그런 호스트에는 아예 설치하지 않고 `tiny`를 비워 둔다(이미 가리키고 있으면 경고한다). 워크로드를 아는 경우 `OLLAMA_MAX_LOADED_MODELS=2 ./ollama/install.sh`로 덮을 수 있다.
2. **GPU wired 한도** — macOS는 GPU가 고정할 수 있는 메모리를 RAM의 ~75%로 막는다(48GB→~36GB, 64GB→~48GB). 35B-A3B nvfp4는 로드 23GB에 창이 차면 +~10GB라 48GB 호스트는 기본 한도에 닿는다. RAM별로 `iogpu.wired_limit_mb`를 정해(48GB→40960, 64GB→57344, 96GB+→RAM−12GB) `sudo sysctl -w`로 즉시 적용하고 `/etc/sysctl.conf`에 기록해 재부팅 후에도 유지한다. 48GB 미만은 35B가 어차피 안 들어가므로 건드리지 않는다. sudo를 거부하면 수동 명령만 안내하고 계속 진행한다.
3. `ollama`가 없으면 `brew install ollama`
4. `com.ollama.serve.plist.template`의 `__HOME__`·ollama 경로·`__MAX_LOADED_MODELS__`를 채워 `~/Library/LaunchAgents/com.ollama.serve.plist` 생성 후 LaunchAgent 등록 (기존 것은 교체)
5. `ollama pull` → `ollama create`로 파생 모델 생성 (가중치 공유, 디스크 추가 없음)
6. **omp 설정** — `omp config path`로 실제 에이전트 디렉터리를 찾아(프로필·`PI_CONFIG_DIR`·XDG를 따른다) `omp/models.yml`을 설치한다. 단 그 파일에 우리가 관리하지 않는 provider(예: `anthropic`)가 있으면 **덮어쓰지 않고** `models.yml.local-llm`으로 남긴다. `config.yml`은 키 존재만 확인한다

수동으로 할 경우 이 디렉터리 안에서:

```bash
ollama pull qwen3.6:35b-a3b-nvfp4
ollama create qwen3.6-coder -f ollama/Modelfile.qwen3.6-coder
mkdir -p ~/Library/Logs/ollama
sed -e "s|__HOME__|$HOME|g" -e "s|__MAX_LOADED_MODELS__|2|g" \
  ollama/com.ollama.serve.plist.template > ~/Library/LaunchAgents/com.ollama.serve.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ollama.serve.plist
```

확인 / 재시작 / 중지:

```bash
curl -s http://127.0.0.1:11434/api/version && ollama ps
launchctl kickstart -k gui/$(id -u)/com.ollama.serve   # 재시작
launchctl bootout gui/$(id -u)/com.ollama.serve        # 중지
```

> brew services start ollama 는 쓰지 않는다. 환경변수를 넘길 수 없고 LaunchAgent와 충돌한다.

### 48GB 맥

macOS 기본 GPU wired 한도는 ~36GB(RAM의 75%)다. `install.sh`가 `iogpu.wired_limit_mb=40960`(OS 몫 8GB)으로 올려 영구화하므로, 그 뒤 상한은 ~40GB.

| 35B-A3B 양자화 | 디스크 | 창 포화 시 | 48GB(한도 40GB) |
|---|---|---|---|
| Q4_K_M / nvfp4 | 22GB | ~33GB | 여유 |
| Q5_K_M | 25GB | ~36GB | 가능 |
| Q6_K | 29GB | ~40GB | 빠듯 — 다른 앱 여유 거의 없음. 불안하면 `num_ctx 32768`(~35GB) |
| Q8_0 | 38GB | ~49GB | 불가 |

- `qwen3.6-coder` 단독 사용 (131K ctx: 로드 23GB, 창이 차면 ~33GB 추정). 27B와 동시 상주는 불가(스왑됨).
- 보조 4B는 `install.sh`가 **설치하지 않는다** — 슬롯이 1이라 호출마다 코더가 왕복 5~10s 스왑하기 때문이다. `modelRoles.tiny`는 비워 두거나 클라우드 소형 모델로 둔다.
- mxfp8(38GB)은 컨텍스트를 줄여도 부적합.
- 그 외 절차는 동일.

## 클라이언트 연결

### oh-my-pi (omp)

omp 설정도 이 저장소가 관리한다. `install.sh`가 `omp/models.yml`을 `~/.omp/agent/models.yml`로 **그대로 설치**하고(기존 내용이 다르면 `.replaced-<타임스탬프>`로 보존), `config.yml`은 **건드리지 않고 키만 확인**한다 — 거기엔 omp 자신이 쓰는 값(`setupVersion`, `theme`, 모델 셀렉터가 저장하는 역할 배정)이 함께 살기 때문이다. 필요한 두 줄은 `omp/config.fragment.yml`에 있다:

```yaml
modelRoles:
  default: ollama/qwen3.6-coder            # 코딩 본체 (35B, 창 131072)
  tiny: ollama-nothink/qwen3.5-aux:latest  # 제목·메모리·분류 (4B, thinking off)
```

provider 설정은 두 엔트리이고 아래 절에 전문이 있다. baseUrl에 `/v1`이 **필수**인 점만 먼저 — 빼면 `POST /responses`가 404다.

- omp 문서 예시는 baseUrl에 `/v1`이 없지만, 실제로는 `/v1`을 붙여야 Responses API(`/v1/responses`)에 닿는다.
- 비대화형 실행(`omp -p "..."`) 시 stdin이 파이프면 EOF를 기다리며 멈춘다 → `</dev/null` 필요.
- 검증: `sandbox/`에 LRU 캐시 구현 + pytest 작성·실행 과제를 `--auto-approve`로 수행, 툴콜 21회, 177초, 8 tests passed.

#### 보조 작업과 압축 (`modelRoles.tiny`, `compactionModel`)

omp는 제목 생성·메모리 질의·사고강도 분류·비정상 종료 감지를 `tiny` 역할로 돌린다(미설정이면 `@smol`). 코더에 맡기면 보조 요청 하나가 thinking 토큰 수천 개를 쓰고, `OLLAMA_NUM_PARALLEL=1`이라 그동안 코딩이 멈춘다.

thinking을 끄는 경로는 하나뿐이다 (qwen3.6-coder 실측, `max_tokens: 300`):

| 요청 필드 | thinking | completion 토큰 |
|---|---|---|
| (없음) | 켜짐 | 300 (상한 소진, 답변 없음) |
| `reasoning: {"effort": "minimal"}` | **켜짐 (무시됨)** | 300 (상한 소진, 답변 없음) |
| `reasoning: {"effort": "none"}` | 꺼짐 | **6** (답변 생성) |

omp의 thinking 레벨은 `minimal|low|medium|high`뿐이고 `none`이 없다 — `--model x:minimal`로는 못 끈다. 필드를 직접 실으려면 `compat.extraBody`를 쓰는데, 이건 **`api: openai-completions`에서만 적용된다**. `openai-responses`로 두면 임의 키까지 전부 body에서 누락된다(실측).

한 서버인데 provider 엔트리가 **두 개**인 이유는 스키마 때문이다:

1. `api`는 provider 레벨 필드다 — `modelOverrides`가 덮을 수 있는 목록(`contextWindow`, `maxTokens`, `compat`, `compactionModel`, `remoteCompaction`, ...)에 `api`가 없다. 모델별로 경로를 갈아탈 수 없다.
2. `extraBody`는 completions 경로에서만 실린다.
3. 코더가 두 역할을 겸한다 — 코딩은 thinking ON, 요약은 OFF. 같은 provider + 같은 모델 id는 compat을 하나만 가지므로 분리가 불가피하다.

반대로 **thinking을 꺼야 하는 호출은 전부 한 엔트리에 모인다** — 제목/메모리/분류(4B)와 압축 요약(코더 자신)은 설정이 같다:

```yaml
providers:
  ollama:                            # 코딩 본체 (thinking ON)
    baseUrl: http://127.0.0.1:11434/v1
    api: openai-responses
    auth: none
    discovery:
      type: ollama
    modelOverrides:
      qwen3.6-coder:latest:
        compactionModel: ollama-nothink/qwen3.6-coder:latest

  ollama-nothink:                    # 생각하면 안 되는 호출 전부
    baseUrl: http://127.0.0.1:11434/v1
    api: openai-completions          # extraBody는 이 경로에서만 실린다
    auth: none
    compat:
      extraBody:
        reasoning_effort: none       # ollama가 유일하게 듣는 값
    models:
      - id: qwen3.6-coder:latest     # 압축 요약 - 이미 로드된 슬롯, 추가 메모리 0
        contextWindow: 131072
        maxTokens: 4096
      - id: qwen3.5-aux:latest       # 제목/메모리/분류
        contextWindow: 8192
        maxTokens: 1024
```

`config.yml`: `modelRoles.tiny: ollama-nothink/qwen3.5-aux:latest`

압축을 4B에 넘기지는 않는다 — 수만 토큰을 요약하는 일이라 세션 기억이 열화된다. 같은 코더를 다른 경로로 부르므로 품질은 35B 그대로이고 thinking만 꺼진다.

**`smol`이 아니라 `tiny`여야 한다.** `tiny`를 비워두면 `@smol`로 폴백하므로 `smol`만 채워도 보조 작업은 돌아간다. 하지만 `smol`은 백그라운드 전용이 아니다 — 모델 스위처 순환 대상(`cycleOrder: [smol, default, slow]`)이고, `--smol` 플래그가 가리키며, **prewalk의 기본 타깃**이다(`--prewalk-into` 기본값이 `smol` 역할). prewalk는 todo 목록이 생긴 뒤 첫 편집에서 활성 모델을 "빠르고 싼" 모델로 갈아타는 기능이라, `smol`에 4B/8K를 걸어두면 그 순간부터 **실제 코드 편집이 4B로 내려간다**. 제목 6토큰 쓰라고 올린 모델에 편집을 넘기는 셈이다. `tiny`에는 그 경로가 없다.

`smol`은 비워두는 편이 안전하다. 채우려면 코딩 가능한 모델이어야 하는데, 로컬에서 그 조건을 만족하는 `qwen3.8-coder`(18GB)를 올리면 `MAX_LOADED_MODELS=2` 상태에서 코더나 보조 중 하나가 내려간다 — 이득이 없다. 클라우드 소형 모델이라면 경합 없이 채울 수 있다.

실증: `modelRoles.default: ollama/qwen3.6-coder`로 툴 3회짜리 과제를 두 번 돌리고(54초 / 29초, 둘 다 정답) `ollama-nothink` 자리에 로깅 프록시를 세웠다. 압축 요청이 `POST /v1/chat/completions`으로 `model: qwen3.6-coder:latest`, `reasoning_effort: "none"`, 시스템 프롬프트 `"Summarize user–AI coding-assistant conversations... Output ONLY the structured summary"`와 함께 도착했고, 세션 엔트리에도 `compaction` 1건이 남았다. 압축의 기본 주체는 **세션 모델 자신**이며(`sameModel: true`), 이 override가 그 경로만 바꾼다. 제목 생성은 `-p` 단발 실행에서는 프로세스가 먼저 끝나 경합에 걸린다(세션 파일의 `title` 엔트리는 생성 시점에 빈 자리표시자로 먼저 기록된다) — 대화형 세션에서 4B로 나가는 것은 별도로 확인했다(`/v1/chat/completions` 854ms, `ollama ps`에 `qwen3.5-aux` 등장).

### Hermes Agent

`~/.hermes/config.yaml`:

```yaml
model:
  default: qwen3.6-coder
  provider: custom
  base_url: http://127.0.0.1:11434/v1
  api_key: ollama            # 아무 값. Ollama는 키를 검사하지 않음

auxiliary:                   # 보조 작업(제목 생성, 메모리 질의, 압축 등) 전부에 적용
  title_generation:
    timeout: 90
    extra_body:
      reasoning:
        effort: none
        enabled: false
  memory_query_rewrite: { ... 동일 ... }
  approval / skills_hub / mcp / triage_specifier / profile_describer / goal_judge / curator / kanban_decomposer: 동일, timeout 90
  compression: 동일, timeout 300
  web_extract: 동일, timeout 360
  vision: 동일, timeout 180
```

**왜 보조 작업의 thinking을 꺼야 하나**: Hermes는 메인 요청과 동시에 제목 생성 같은 보조 요청을 보낸다. thinking이 켜진 채로 두면 제목 하나에 1,000~6,000토큰을 생성하다 타임아웃(500)이 나고, GPU를 나눠 쓰는 메인 요청까지 느려진다. 끄고 나서 턴당 72s → 2~3s.

**`reasoning_effort` 단축키가 아니라 `extra_body.reasoning`을 써야 하는 이유**: Hermes의 `auxiliary.<task>.reasoning_effort: none`은 `reasoning_effort: "none"` **과** `reasoning: {"enabled": false}`를 함께 보내는데, Ollama는 `reasoning` 객체가 있으면 그것만 보고 `effort`가 없으면 기본(thinking ON)으로 처리한다. 실측:

| 요청 필드 | thinking |
|---|---|
| `reasoning_effort: "none"` | 꺼짐 |
| `reasoning: {"effort": "none"}` | 꺼짐 |
| `reasoning: {"enabled": false}` | **켜짐 (무시됨)** |
| `reasoning_effort: "none"` + `reasoning: {"enabled": false}` | **켜짐** |

Hermes 시스템 프롬프트는 약 23K 토큰이라 세션 첫 턴은 콜드 prefill ~35~70초가 걸린다. 이후 턴은 프리픽스 캐시로 1.5K 정도만 재처리된다.

자동 구성 대안: `ollama launch hermes` / `ollama launch omp` ([Hermes](https://docs.ollama.com/integrations/hermes), [Oh My Pi](https://docs.ollama.com/integrations/oh-my-pi)).

## 알려진 제약

- **`response_format: json_schema`가 Ollama MLX에서 무시된다.** 스키마를 보내도 일반 텍스트로 응답하는 경우가 있다(thinking off일 때 재현). Hermes 제목 생성은 텍스트 폴백 파싱이 있어 동작하지만, 엄격한 구조화 출력이 필요하면 프롬프트로 강제해야 한다.
- Ollama 프리픽스 캐시: `tools`가 포함된 요청에서 사용자 질문이 바뀌면 약 절반(15K 중 ~8K)을 재처리한다(TTFT ~13s). 툴 없는 요청은 완전 적중(0.2s). `NUM_PARALLEL` 슬롯과는 무관함을 확인.
- 35B-A3B에서 MTP 추측 디코딩은 드래프트가 거의 발생하지 않는다(로그 `drafted=1~40`). 속도는 기본 디코드로 나오는 것.
- **긴 에이전트 턴이 `Request was aborted`로 죽는다 (omp + ollama, 미해결).** 도구를 여러 번
  쓰는 작업에서 재현된다. 서버는 무죄다 — 로그의 모든 요청이 `200 OK`이고 마지막 요청은
  11,651 토큰 프리필에 31.9s(≈430 tok/s)를 쓰고 정상 응답했다. 끊는 쪽은 클라이언트이고,
  다음 요청을 **보내기 전에** 끊으므로 서버 로그에 흔적이 없다. `--mode json`으로 받아도
  `exit 0`에 오류 이벤트가 없다(리포팅 공백).
  - 중단 지점(당시 qwen3.6-coder, `num_ctx 65536 / num_predict 32768`): `maxTokens` 미지정 시
    **35,676 토큰**. `65536 − 32768 ≈ 32.7K`가 입력 상한이라는 계산과 맞는다. `modelOverrides.maxTokens:
    8192`을 넣으면 **37,081**까지 올라간다. 지금은 Modelfile 자체가 `131072 / 8192`라 이 상한이 ~123K다.
  - 효과 없음: `providers.streamFirstEventTimeoutSeconds: 600`, 컴팩션 전략 교체
    (`snapcompact` ↔ `context-full`), `keepRecentTokens`/`thresholdPercent` 축소,
    `--thinking off`, `api: openai-completions` 경로(`ollama-nothink`).
  - 부분 효과: `--external-thinking`으로 생존 시간이 38s → 85s. 모델을 바꾸면 지점만
    옮겨진다(qwen3.8-coder는 4m34s 뒤 중단).
  - 컴팩션은 정상 작동한다(`auto_compaction_start/end`, `dead-end recovery: elided 11 heavy
    blocks ~13,143 tokens`). 즉 컨텍스트 관리의 실패가 아니라, 그 위에서 요청이 끊긴다.
  - 회피책: 긴 작업을 **짧은 세션 여러 개**로 쪼개고(세션마다 컨텍스트 초기화), 판단이
    필요한 단계는 명령으로 기계화한다. 한 세션 안에서 스스로 쪼개게 하는 것은 지금 불가능.

## 검증 (`make verify`)

설정·문서·벤치 기록은 전부 표준이 있고, 표준은 기계로 검사한다. `sandbox/.omp/`(omp 용 하네스)의 구조를 Claude Code 규격(`.claude/rules/` 경로 조건 규칙 + `.claude/settings.json` 훅)으로 옮긴 것이다. 공식 문서: [hooks](https://code.claude.com/docs/en/hooks.md), [rules](https://code.claude.com/docs/en/memory.md).

```
make help              # 타깃 목록
make verify            # 모든 검사 (커밋 전 게이트). 순수 파일 읽기, node 24+ 필요, 의존성 없음
make check-<name>      # 검사 하나
```

| 이름 | 검사 대상 | 잡는 것 |
|---|---|---|
| `bench-results` | `bench/` | 파일명 `<date>.<s1|s2>.<subject>`, 플랫, 5절 순서, 결과 표 필수 열, n 표기, n=1 잠정, README 인덱스 |
| `ollama-modelfile` | `ollama/` | Create 주석, `num_predict < num_ctx`, 샘플링 출처 주석, install.sh 의 create/pull |
| `omp-models` | `omp/` | 두 provider 분리, Modelfile 과 창/출력 일치, oMLX 프로파일과 일치, extraBody 는 completions 만, 참조 실재 |
| `omlx-config` | `omlx/` | `reasoning_parser`, MTP 비중립값 금지, 프로파일 시그니처 동일, 드래프터 다운로드, `safe` 티어 |
| `docs-sync` | `CLAUDE.md`, `README.md` | 기본 코더 표기 = `modelRoles.default`, 인용 절 실재, 파일 목록 완비 |
| `skills` | `.claude/skills/` | 프런트매터 name/description, CLAUDE.md 등재 |
| `harness` | `.claude/`, `Makefile` | 규칙↔검사↔타깃↔verify 이름 계약, settings.json 배선, 훅 스모크 |
| `autostart` | `ollama/`, `omlx/` ↔ 호스트 | 두 서버의 자동 시작·재시작이 **둘 다 꺼짐**: 템플릿 RunAtLoad/KeepAlive false, install.sh 에 brew services 없음, brew services 미기동, homebrew plist 없음, 전역 launchd·로그인 항목 없음, oMLX `auto_start_on_launch: false` |
| `live-sync` | `ollama/`, `omlx/`, `omp/` ↔ 호스트 | `~/.omp/agent` models.yml 동일·config.yml modelRoles, `~/.omlx` JSON 동일·settings 값·HF 캐시, Ollama plist·(서버가 떠 있으면) `ollama show` 파라미터. 미설치는 skip |

훅(`.claude/settings.json`): `PreToolUse Bash` 가 금지 명령(brew services 로 Ollama 기동, sudo, ollama pull, hf download, install.sh)을 deny, `PreToolUse Edit|Write` 가 레이아웃 위반(bench/ 하위 디렉터리 등)을 deny, `PostToolUse Edit|Write` 가 편집 파일에 매치되는 규칙의 검사를 돌려 위반을 모델에 돌려준다. 규칙 파일의 `paths` 가 곧 훅의 트리거다.

## 파일

```
Makefile                           # make verify / check-<name> — 검증 진입점
ollama/
  install.sh                       # 전체 설치 (멱등: 서버 + 모델 + omp 설정). --with-27b, --with-qwen3-coder
  Modelfile.qwen3.6-coder
  Modelfile.qwen3.5-aux
  Modelfile.qwen3.8-coder
  Modelfile.qwen3-coder            # 벤치 비교용 instruct 코더 (옵션)
  com.ollama.serve.plist.template  # __HOME__ 치환 후 LaunchAgents에 설치 (RunAtLoad/KeepAlive 꺼짐, kickstart 로 기동)
bench/
  README.md                        # 결과 기록 표준 + 인덱스 + 종합. 수행 환경(스크립트)은 두지 않는다
  <date>.<s1|s2>.<subject>.md/.json # 캠페인별 기록과 원본
sandbox/                           # 2단계 피험자 트리 — fast-api-standard 사본, 포트 분리 (SANDBOX.md)
.claude/
  settings.json                    # 훅 배선 (PreToolUse Bash / Edit|Write, PostToolUse Edit|Write)
  rules/<name>.md                  # 표준 (paths 프런트매터 = 로드 조건 = 훅 트리거)
  hooks/check-<name>.ts            # 규칙마다 검사 하나. lib/harness.ts(공용), lib/hook-io.ts(훅 프로토콜)
  hooks/pre-bash.ts, pre-write.ts, post-edit.ts  # 훅 진입점
  skills/bench-model, llm-bench, add-model  # 1단계 단발 벤치 / 2단계 장기 세션 벤치(runner.ts, tasks/, reference/) / 모델 추가
CLAUDE.md                          # Claude 작업 규칙과 환경 사실
omlx/
  install.sh                       # ~/.omlx 설정 동기화 + 서비스 잔재 정리 + 앱 서버 재시작 (멱등, 앱은 DMG 로 먼저. 모델은 앱 스토어 관리)
  model_settings.json              # 모델별 설정(창/샘플링/MTP/thinking budget) → ~/.omlx/ 로 설치
  model_profiles.json              # :mtp / :nothink 프로파일 → ~/.omlx/ 로 설치
  smoke.sh                         # 베이크 후 검증(서빙·응답·reasoning 분리·MTP 발화·서버가 보는 설정값) — `make smoke`
omp/
  models.yml                       # ~/.omp/agent/models.yml 로 그대로 설치
  config.fragment.yml              # config.yml 에 병합할 조각 (덮어쓰지 않음)
```

## 참고 자료

- [Ollama is now powered by MLX on Apple Silicon](https://ollama.com/blog/mlx)
- [Ollama Releases](https://github.com/ollama/ollama/releases) — MTP 추측 디코딩, MLX 태그
- [Ollama FAQ](https://docs.ollama.com/faq) · [Thinking](https://docs.ollama.com/capabilities/thinking) · [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Hermes — Run Local LLMs on Mac](https://hermes-agent.nousresearch.com/docs/guides/local-llm-on-mac)
- [oh-my-pi models.md](https://github.com/can1357/oh-my-pi/blob/main/docs/models.md)
- [jundot/omlx](https://github.com/jundot/omlx)
