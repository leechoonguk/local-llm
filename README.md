# Local LLM Setup — Ollama on Apple Silicon

Hermes Agent / oh-my-pi(omp) 용 로컬 LLM 서버 구성. Mac mini M4 Pro 64GB 기준이며, 48GB 맥에서도 동일하게 재현 가능하다.

## 왜 Ollama인가

oMLX와 Ollama를 같은 모델(Qwen3.8-27B NVFP4)로 직접 벤치한 결과 Ollama로 선정했다. 2026-08-20 기준 둘 다 Apple Silicon에서 MLX 엔진을 쓰므로 엔진 차이는 없고, 실측 차이는 다음과 같았다.

| 항목 | oMLX (MTP 적용) | Ollama 0.32.14 |
|---|---|---|
| 15K 프롬프트 캐시 적중 시 TTFT | 11~17s (고정) | **0.2~0.6s** |
| 툴콜 생성 속도 | 19 tok/s | **23 tok/s** |
| `response_format: json_schema` | 12 tok/s (추측 디코딩 폴백) | **22.5 tok/s** (유지) |
| Hermes / omp 공식 통합 | LM Studio 호환 방식 우회 | 네이티브 (`ollama launch`) |
| 단점 | — | 프리픽스 캐시 미스가 간헐적 (같은 15K 프리픽스를 절반 재프리필, 80~90s) |

oMLX는 `thinking_budget_enabled`가 켜져 있으면 Qwen VLM 어댑터에서 MTP가 통째로 비활성화되는 함정이 있었다(기본 설정 상태에서는 MTP가 한 번도 동작하지 않았음).

## 모델

| 모델 | 베이스 | 크기 | 용도 |
|---|---|---|---|
| `ornith-coder-q5` | `hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q5_K_M` (Qwen3.5-MoE 아키텍처, 35B, 활성 3B, 5bit) | 26GB | **주력**. 코딩/에이전트. 아래 "Ornith-1.5 검증" 참고 |
| `qwen3.6-coder` | `qwen3.6:35b-a3b-nvfp4` (MoE 35B, 활성 3B, 4bit) | 23GB | 이전 주력. 셀렉터에서 교체 가능. 토큰 속도는 더 빠름(MLX 경로) |
| `qwen3.8-coder` | `qwen3.8:27b-nvfp4` (dense 27B, 4bit) | 18GB | 무거운 추론. prefill 느림 |
| `qwen3.5-aux` | `qwen3.5:4b-nvfp4` (dense 4B, 4bit) | 4GB | 보조 작업(제목/메모리/분류). 코더와 동시 상주 |

### Ornith-1.5 검증 (2026-08-23, 64GB, 단일 로드, 65K ctx, thinking on, temp 0.6)

실행 테스트로 채점하는 코딩 과제 4개(LRU+TTL 캐시, 구간 병합 버그픽스, nginx 로그 파서, debounce)를 세 모델에 1회씩 돌렸다.

| | qwen3.6-coder (nvfp4) | ornith Q4_K_M | ornith Q5_K_M |
|---|---|---|---|
| 로드 직후 | 23GB | 23GB | 26GB |
| 생성 속도 | 65 tok/s | 49 tok/s | 42 tok/s |
| 정답률 | 3/4 | 3/4 | 3/4 |
| 4과제 합산 시간 | 766s | 314s | 359s |

- 정확도는 동률. debounce(leading+trailing+cancel)는 셋 다 다른 로직 버그로 실패.
- Ornith의 실익은 **추론 토큰 절약**: 버그픽스 과제에서 qwen은 19K 토큰을 생각했고 ornith는 257 토큰으로 끝냈다. 토큰당 속도가 GGUF라 25~35% 느린데도 응답 시간은 2~5배 짧다 — 에이전트 턴 시간이 그대로 줄어든다.
- 토큰 속도 차이는 모델이 아니라 포맷(nvfp4=MLX 경로 / GGUF=llama.cpp 경로). 공식 Ollama 태그는 Q4_K_M뿐이라 Q5는 HF GGUF에서 받는다.
- Q4 vs Q5는 n=1이라 변별 불가. 메모리 여유가 있어 Q5를 채택했다. 48GB에서는 로드 26GB + 창이 차면 ~36GB로 `iogpu.wired_limit_mb=40960` 안에 든다.
- 과제 4개 1회라 통계적 확신은 낮다. 자체 보고 벤치마크(Qwen3.6-35B 대비 전 항목 우위)만큼의 압도는 관찰되지 않았다.

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
| `num_ctx` | 65536 (3.6) / 32768 (3.8) / 8192 (aux) | Ollama 기본 4096은 에이전트용으로 불가. 64GB에서 코더 두 개 + 보조가 동시 상주 가능한 조합 |
| `num_predict` | 32768 | Qwen 권장 출력 길이. **thinking 토큰을 포함**하므로 작게 주면 답변이 잘린다 |

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

`com.ollama.serve.plist.template` → `~/Library/LaunchAgents/com.ollama.serve.plist` — 로그인 시 자동 시작, 비정상 종료 시 재시작.

| 환경변수 | 값 | 이유 |
|---|---|---|
| `OLLAMA_HOST` | 127.0.0.1:11434 | |
| `OLLAMA_KEEP_ALIVE` | 1h | 기본 5분이면 대화 사이에 모델이 내려가 매번 5~11초 재로드 |
| `OLLAMA_NUM_PARALLEL` | 1 | 슬롯당 KV가 잡히므로 2→1로 64K ctx 기준 ~5GB 절약. 보조 요청은 thinking off라 직렬화돼도 0.4~1s |
| `OLLAMA_MAX_LOADED_MODELS` | 2 (64GB+) / 1 (그 아래) | 코더 + 보조 모델 동시 상주. `install.sh`가 RAM을 보고 채운다 — 1이면 보조 호출마다 코더가 내려간다(왕복 5~10s). 27B는 여전히 쓸 때만 스왑 |
| `iogpu.wired_limit_mb` (sysctl) | 48GB→40960, 64GB→57344, 96GB+→RAM−12GB, 그 아래 0(기본) | env가 아니라 macOS 커널 한도. 기본값(RAM의 ~75%)을 넘는 모델은 레이어가 CPU로 내려가 속도가 급락한다. `install.sh`가 RAM을 보고 즉시 적용 + `/etc/sysctl.conf`로 영구화(sudo). `OLLAMA_WIRED_LIMIT_MB`로 덮어쓸 수 있다 |

컨텍스트 길이는 env(`OLLAMA_CONTEXT_LENGTH`)가 아니라 Modelfile `num_ctx`로 관리한다. `/v1` OpenAI 호환 API는 `num_ctx`를 요청에 실을 수 없기 때문이다.

로그: `~/Library/Logs/ollama/ollama.log` — `speculative decode stats` 라인으로 MTP 동작 확인 가능.

## 설치 / 재현

```bash
git clone https://github.com/leechoonguk/local-llm.git && cd local-llm
./ollama/install.sh              # ornith-coder-q5 + qwen3.6-coder
./ollama/install.sh --with-27b   # qwen3.8-coder 까지
```

`install.sh`가 하는 일(재실행 안전):

1. **호스트 검사** — arm64 macOS가 아니면 즉시 중단한다(MLX 태그는 Apple Silicon 전용. 안 막으면 수십 GB를 내려받고 나서 실패한다). RAM으로 두 가지를 정한다: `OLLAMA_MAX_LOADED_MODELS`(64GB 이상 2, 그 아래 1)와 **보조 모델 설치 여부**. 슬롯이 하나면 보조 호출마다 코더가 왕복 5~10s 스왑하므로 손해다 — 그런 호스트에는 아예 설치하지 않고 `tiny`를 비워 둔다(이미 가리키고 있으면 경고한다). 워크로드를 아는 경우 `OLLAMA_MAX_LOADED_MODELS=2 ./ollama/install.sh`로 덮을 수 있다.
2. **GPU wired 한도** — macOS는 GPU가 고정할 수 있는 메모리를 RAM의 ~75%로 막는다(48GB→~36GB, 64GB→~48GB). 35B-A3B를 64K ctx로 올리면 Q4_K_M 33GB, Q5_K_M ~36GB, Q6_K ~40GB라 48GB 호스트는 한도를 넘는다. RAM별로 `iogpu.wired_limit_mb`를 정해(48GB→40960, 64GB→57344, 96GB+→RAM−12GB) `sudo sysctl -w`로 즉시 적용하고 `/etc/sysctl.conf`에 기록해 재부팅 후에도 유지한다. 48GB 미만은 35B가 어차피 안 들어가므로 건드리지 않는다. sudo를 거부하면 수동 명령만 안내하고 계속 진행한다.
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

| 35B-A3B 양자화 | 디스크 | 64K ctx 로드 | 48GB(한도 40GB) |
|---|---|---|---|
| Q4_K_M / nvfp4 | 22GB | ~33GB | 여유 |
| Q5_K_M | 25GB | ~36GB | 가능 |
| Q6_K | 29GB | ~40GB | 빠듯 — 다른 앱 여유 거의 없음. 불안하면 `num_ctx 32768`(~35GB) |
| Q8_0 | 38GB | ~49GB | 불가 |

- `qwen3.6-coder` 단독 사용 (64K ctx ≈ 37GB). 27B와 동시 상주는 불가(스왑됨).
- 보조 4B는 `install.sh`가 **설치하지 않는다** — 슬롯이 1이라 호출마다 코더가 왕복 5~10s 스왑하기 때문이다. `modelRoles.tiny`는 비워 두거나 클라우드 소형 모델로 둔다.
- mxfp8(38GB)은 컨텍스트를 줄여도 부적합.
- 그 외 절차는 동일.

## 클라이언트 연결

### oh-my-pi (omp)

omp 설정도 이 저장소가 관리한다. `install.sh`가 `omp/models.yml`을 `~/.omp/agent/models.yml`로 **그대로 설치**하고(기존 내용이 다르면 `.replaced-<타임스탬프>`로 보존), `config.yml`은 **건드리지 않고 키만 확인**한다 — 거기엔 omp 자신이 쓰는 값(`setupVersion`, `theme`, 모델 셀렉터가 저장하는 역할 배정)이 함께 살기 때문이다. 필요한 두 줄은 `omp/config.fragment.yml`에 있다:

```yaml
modelRoles:
  default: ollama/ornith-coder-q5          # 코딩 본체 (35B, 창 65536)
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
        contextWindow: 65536
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
  - 중단 지점(qwen3.6-coder): `maxTokens` 미지정 시 **35,676 토큰**. `num_ctx 65536 −
    num_predict 32768 ≈ 32.7K`가 입력 상한이라는 계산과 맞는다. `modelOverrides.maxTokens:
    8192`을 넣으면 **37,081**까지 올라간다 — 그래서 그 값은 넣어 두었다.
  - 효과 없음: `providers.streamFirstEventTimeoutSeconds: 600`, 컴팩션 전략 교체
    (`snapcompact` ↔ `context-full`), `keepRecentTokens`/`thresholdPercent` 축소,
    `--thinking off`, `api: openai-completions` 경로(`ollama-nothink`).
  - 부분 효과: `--external-thinking`으로 생존 시간이 38s → 85s. 모델을 바꾸면 지점만
    옮겨진다(qwen3.8-coder는 4m34s 뒤 중단).
  - 컴팩션은 정상 작동한다(`auto_compaction_start/end`, `dead-end recovery: elided 11 heavy
    blocks ~13,143 tokens`). 즉 컨텍스트 관리의 실패가 아니라, 그 위에서 요청이 끊긴다.
  - 회피책: 긴 작업을 **짧은 세션 여러 개**로 쪼개고(세션마다 컨텍스트 초기화), 판단이
    필요한 단계는 명령으로 기계화한다. 한 세션 안에서 스스로 쪼개게 하는 것은 지금 불가능.

## 파일

```
ollama/
  install.sh                       # 전체 설치 (멱등: 서버 + 모델 + omp 설정)
  Modelfile.ornith-coder-q5
  Modelfile.qwen3.6-coder
  Modelfile.qwen3.5-aux
  Modelfile.qwen3.8-coder
  com.ollama.serve.plist.template  # __HOME__ 치환 후 LaunchAgents에 설치
bench/
  run.py / report.py               # 코딩 모델 검증 하네스 (단일 로드, 실행 테스트 채점). results/는 gitignore
  tasks/                           # tN_prompt.md + tN_test.*
.claude/
  skills/bench-model, add-model    # Claude Code 스킬: 모델 검증 / 모델 추가 절차
  hooks/omp-sync-reminder.sh       # omp 설정·Modelfile 편집 시 라이브 반영 알림
CLAUDE.md                          # Claude 작업 규칙과 환경 사실
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
