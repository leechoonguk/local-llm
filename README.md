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
| `qwen3.6-coder` | `qwen3.6:35b-a3b-nvfp4` (MoE 35B, 활성 3B, 4bit) | 23GB | **주력**. 코딩/에이전트 |
| `qwen3.8-coder` | `qwen3.8:27b-nvfp4` (dense 27B, 4bit) | 18GB | 무거운 추론. prefill 느림 |

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
| `num_ctx` | 65536 (3.6) / 32768 (3.8) | Ollama 기본 4096은 에이전트용으로 불가. 64GB에서 두 모델 동시 상주 가능한 조합 |
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
| `OLLAMA_MAX_LOADED_MODELS` | 1 | Hermes·omp 모두 qwen3.6-coder 사용. 27B는 쓸 때만 스왑(5~10s) |

컨텍스트 길이는 env(`OLLAMA_CONTEXT_LENGTH`)가 아니라 Modelfile `num_ctx`로 관리한다. `/v1` OpenAI 호환 API는 `num_ctx`를 요청에 실을 수 없기 때문이다.

로그: `~/Library/Logs/ollama/ollama.log` — `speculative decode stats` 라인으로 MTP 동작 확인 가능.

## 설치 / 재현

```bash
git clone https://github.com/leechoonguk/local-llm.git && cd local-llm
./ollama/install.sh              # qwen3.6-coder 만
./ollama/install.sh --with-27b   # qwen3.8-coder 까지
```

`install.sh`가 하는 일(재실행 안전):

1. `ollama`가 없으면 `brew install ollama`
2. `com.ollama.serve.plist.template`의 `__HOME__`과 ollama 경로를 채워 `~/Library/LaunchAgents/com.ollama.serve.plist` 생성 후 LaunchAgent 등록 (기존 것은 교체)
3. `ollama pull` → `ollama create`로 파생 모델 생성 (가중치 공유, 디스크 추가 없음)

수동으로 할 경우 이 디렉터리 안에서:

```bash
ollama pull qwen3.6:35b-a3b-nvfp4
ollama create qwen3.6-coder -f ollama/Modelfile.qwen3.6-coder
mkdir -p ~/Library/Logs/ollama
sed "s|__HOME__|$HOME|g" ollama/com.ollama.serve.plist.template > ~/Library/LaunchAgents/com.ollama.serve.plist
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

Ollama가 GPU 가용 메모리를 RAM의 약 90%로 잡으므로 상한은 ~43GB.

- `qwen3.6-coder` 단독 사용 (64K ctx ≈ 37GB). 27B와 동시 상주는 불가(스왑됨).
- mxfp8(38GB)은 컨텍스트를 줄여도 부적합.
- 그 외 절차는 동일.

## 클라이언트 연결

### oh-my-pi (omp)

`~/.omp/agent/models.yml`:

```yaml
providers:
  ollama:
    baseUrl: http://127.0.0.1:11434/v1   # /v1 필수 — 없으면 POST /responses 404
    api: openai-responses
    auth: none
    discovery:
      type: ollama                       # /api/show 로 컨텍스트 길이 자동 감지
```

`~/.omp/agent/config.yml`: `modelRoles.default: ollama/qwen3.6-coder`

- omp 문서 예시는 baseUrl에 `/v1`이 없지만, 실제로는 `/v1`을 붙여야 Responses API(`/v1/responses`)에 닿는다.
- 비대화형 실행(`omp -p "..."`) 시 stdin이 파이프면 EOF를 기다리며 멈춘다 → `</dev/null` 필요.
- 검증: `sandbox/`에 LRU 캐시 구현 + pytest 작성·실행 과제를 `--auto-approve`로 수행, 툴콜 21회, 177초, 8 tests passed.

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

## 파일

```
ollama/
  install.sh                       # 전체 설치 (멱등)
  Modelfile.qwen3.6-coder
  Modelfile.qwen3.8-coder
  com.ollama.serve.plist.template  # __HOME__ 치환 후 LaunchAgents에 설치
```

## 참고 자료

- [Ollama is now powered by MLX on Apple Silicon](https://ollama.com/blog/mlx)
- [Ollama Releases](https://github.com/ollama/ollama/releases) — MTP 추측 디코딩, MLX 태그
- [Ollama FAQ](https://docs.ollama.com/faq) · [Thinking](https://docs.ollama.com/capabilities/thinking) · [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Hermes — Run Local LLMs on Mac](https://hermes-agent.nousresearch.com/docs/guides/local-llm-on-mac)
- [oh-my-pi models.md](https://github.com/can1357/oh-my-pi/blob/main/docs/models.md)
- [jundot/omlx](https://github.com/jundot/omlx)
