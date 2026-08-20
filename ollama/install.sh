#!/bin/bash
# Ollama local LLM setup for Apple Silicon (Hermes Agent / oh-my-pi).
# Idempotent: safe to re-run. Usage: ./ollama/install.sh [--with-27b]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WITH_27B=0
[[ "${1:-}" == "--with-27b" ]] && WITH_27B=1

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
if [[ $WITH_27B -eq 1 ]]; then
  ollama pull qwen3.8:27b-nvfp4
  ollama create qwen3.8-coder -f "$HERE/Modelfile.qwen3.8-coder"
fi

echo
ollama list
echo
echo "done. test: ollama run qwen3.6-coder 'Reply with exactly: OK'"
