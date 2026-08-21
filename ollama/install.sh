#!/bin/bash
# Ollama local LLM setup for Apple Silicon (Hermes Agent / oh-my-pi).
# Idempotent: safe to re-run. Usage: ./ollama/install.sh [--with-27b]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WITH_27B=0
[[ "${1:-}" == "--with-27b" ]] && WITH_27B=1

# --- Host preconditions -----------------------------------------------------
# MLX 태그(nvfp4/mxfp8)는 Apple Silicon에서만 동작한다. Intel 맥에서 이 스크립트를
# 끝까지 돌리면 41GB를 내려받고 나서 실패한다 - 먼저 막는다.
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Apple Silicon (arm64 macOS) 전용이다: $(uname -s) $(uname -m)" >&2
  exit 1
fi
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
# 64K가 찬 코더는 ~37GB까지 자란다(실측: 로드 직후 23GB, 세션 누적 27GB). 보조
# 4B(~5GB)와 동시 상주는 64GB 이상에서만 안전하고, 그 아래에서는 슬롯을 1로 두어
# 스왑을 감수하는 편이 OOM보다 낫다. 워크로드를 아는 사용자는 env로 덮을 수 있다.
MAX_LOADED="${OLLAMA_MAX_LOADED_MODELS:-}"
if [[ -z "$MAX_LOADED" ]]; then
  if (( RAM_GB >= 64 )); then MAX_LOADED=2; else MAX_LOADED=1; fi
fi
# 슬롯이 하나면 보조 모델은 손해다: 호출마다 코더가 내려갔다 올라온다(왕복 5~10s).
# 그런 호스트에는 아예 설치하지 않고 `tiny`를 비워 둔다.
if (( MAX_LOADED >= 2 )); then WITH_AUX=1; else WITH_AUX=0; fi
echo "host: ${RAM_GB}GB RAM -> OLLAMA_MAX_LOADED_MODELS=$MAX_LOADED, 보조 모델 $([[ $WITH_AUX -eq 1 ]] && echo 설치 || echo 생략)"

OLLAMA_BIN="$(command -v ollama || true)"
if [[ -z "$OLLAMA_BIN" ]]; then
  echo "ollama not found — installing via Homebrew"
  brew install ollama
  OLLAMA_BIN="$(command -v ollama)"
fi
echo "ollama: $OLLAMA_BIN ($($OLLAMA_BIN --version 2>/dev/null | head -1))"

# --- LaunchAgent (persistent server with tuned env) -------------------------
LABEL=com.ollama.serve
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/ollama"
sed -e "s|__HOME__|$HOME|g" -e "s|/opt/homebrew/bin/ollama|$OLLAMA_BIN|g" \
  -e "s|__MAX_LOADED_MODELS__|$MAX_LOADED|g" \
  "$HERE/$LABEL.plist.template" > "$PLIST"
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$LABEL"
  for _ in $(seq 1 40); do   # wait until launchd has fully unloaded it
    launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
    sleep 0.25
  done
fi
pkill -f "ollama serve" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST"
for _ in $(seq 1 20); do
  curl -sf http://127.0.0.1:11434/api/version >/dev/null && break
  sleep 0.5
done
echo "server: $(curl -s http://127.0.0.1:11434/api/version)"

# --- Models -----------------------------------------------------------------
ollama pull qwen3.6:35b-a3b-nvfp4
ollama create qwen3.6-coder -f "$HERE/Modelfile.qwen3.6-coder"
if [[ $WITH_AUX -eq 1 ]]; then
  ollama pull qwen3.5:4b-nvfp4
  ollama create qwen3.5-aux -f "$HERE/Modelfile.qwen3.5-aux"
fi
if [[ $WITH_27B -eq 1 ]]; then
  ollama pull qwen3.8:27b-nvfp4
  ollama create qwen3.8-coder -f "$HERE/Modelfile.qwen3.8-coder"
fi

# --- omp config -------------------------------------------------------------
# models.yml is entirely ours (providers, thinking-off routing) so it is
# installed verbatim. config.yml also holds omp's own state, so it is only
# checked - never overwritten.
ROOT="$(cd "$HERE/.." && pwd)"
# 에이전트 디렉터리는 프로필·PI_CONFIG_DIR·XDG에 따라 움직인다. omp가 직접
# 알려주는 값을 쓰고, 없을 때만 기본 경로로 떨어진다.
OMP_DIR=""
if command -v omp >/dev/null 2>&1; then
  OMP_DIR="$(omp config path 2>/dev/null | tail -1 || true)"
fi
[[ -n "$OMP_DIR" && -d "$OMP_DIR" ]] || OMP_DIR="$HOME/.omp/agent"
if [[ -d "$OMP_DIR" ]]; then
  SRC="$ROOT/omp/models.yml"
  DST="$OMP_DIR/models.yml"
  # 다른 PC의 models.yml에는 클라우드 provider가 들어 있을 수 있다. 통째로
  # 덮으면 그 인증 경로가 사라지므로, 우리가 관리하지 않는 provider가 보이면
  # 설치를 멈추고 병합용 사본만 남긴다.
  FOREIGN=""
  if [[ -f "$DST" ]]; then
    FOREIGN="$(sed -n 's/^  \([A-Za-z0-9_.-]*\):.*/\1/p' "$DST" \
      | grep -vxE 'ollama|ollama-nothink' | tr '\n' ' ' || true)"
  fi
  if [[ -n "${FOREIGN// /}" ]]; then
    cp "$SRC" "$DST.local-llm"
    echo "omp: models.yml에 관리 대상이 아닌 provider가 있다 (${FOREIGN%% }) - 덮어쓰지 않았다"
    echo "omp: 우리 설정은 $DST.local-llm 에 두었다 - providers 아래로 병합할 것"
  else
    if [[ -f "$DST" ]] && ! cmp -s "$SRC" "$DST"; then
      KEEP="$DST.replaced-$(date +%Y%m%d%H%M%S)"
      cp "$DST" "$KEEP"
      echo "omp: models.yml differed - previous copy kept at $KEEP"
    fi
    cp "$SRC" "$DST"
    echo "omp: installed models.yml into $OMP_DIR (providers: ollama, ollama-nothink)"
  fi
  CFG="$OMP_DIR/config.yml"
  REQUIRED=("default: ollama/qwen3.6-coder")
  if [[ $WITH_AUX -eq 1 ]]; then
    REQUIRED+=("tiny: ollama-nothink/qwen3.5-aux:latest")
  fi
  for pair in "${REQUIRED[@]}"; do
    if ! grep -qF "$pair" "$CFG" 2>/dev/null; then
      echo "omp: config.yml lacks '$pair' - merge omp/config.fragment.yml by hand"
    fi
  done
  if [[ $WITH_AUX -eq 0 ]] && grep -qF "tiny: ollama-nothink" "$CFG" 2>/dev/null; then
    echo "omp: 이 호스트에는 보조 모델을 설치하지 않았는데 config.yml이 tiny로 가리킨다"
    echo "omp: 그 줄을 지우거나 클라우드 소형 모델로 바꿀 것"
  fi
else
  echo "omp: $OMP_DIR not found - skipping (install oh-my-pi first)"
fi

echo
ollama list
echo
echo "done. test: ollama run qwen3.6-coder 'Reply with exactly: OK'"
