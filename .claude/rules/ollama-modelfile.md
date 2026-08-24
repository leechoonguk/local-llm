---
paths:
  - "ollama/**"
---

# Ollama Modelfile · install.sh

`ollama/Modelfile.<name>` 은 Ollama 경로의 모델 정의이고 `ollama/install.sh` 가 그것을 만든다. 둘은 항상 같이 움직인다 — `make check-ollama-modelfile`. 새 모델은 `/add-model` 절차로 5곳(Modelfile, install.sh, models.yml, config.fragment.yml, README)을 한 번에 맞춘다.

## Modelfile
- 파일명 `Modelfile.<name>`, `<name>` 은 소문자·숫자·점·하이픈(`qwen3.6-coder`, `qwen3.5-aux`).
- 헤더 주석에 정확히 `Create: ollama create <name> -f ollama/Modelfile.<name>` 한 줄.
- `FROM` 1개. Ollama 태그면 install.sh 가 그 태그를 `ollama pull` 한다.
- `PARAMETER num_ctx` / `num_predict` 는 정수, **num_predict < num_ctx**(입력 상한 = num_ctx − num_predict). `num_ctx` 는 Modelfile 로만 관리한다 — `/v1` API 는 요청에 실을 수 없다.
- 샘플링(`temperature`, `top_p`, `top_k`)은 모델 카드 권장값을 따르고, 주석에 출처를 남긴다("권장", "출처", "모델 카드", "official" 중 하나가 주석에 있어야 한다). 형제 모델과 맞추겠다고 덮지 않는다 — 통제할 것은 창과 출력이다.
- 실측으로 정한 값(창, 출력)은 근거를 주석에 날짜와 함께 남긴다.

## install.sh
- Modelfile 마다 `ollama create <name> -f "$HERE/Modelfile.<name>"` 이 있다. 기본이 아닌 모델은 `--with-…` 옵션 블록 안에 둔다.
- LaunchAgent(`com.ollama.serve`)를 `launchctl bootstrap` + `kickstart` 한다. 템플릿은 `RunAtLoad`/`KeepAlive` false(자동 시작·재시작 금지, `autostart.md`). **`brew services start ollama` 금지**(`pre-bash` 훅도 막는다).
- sudo(`iogpu.wired_limit_mb`)와 대용량 pull 이 들어 있으므로 실행은 사용자가 한다.
