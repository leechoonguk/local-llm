#!/bin/bash
# PostToolUse(Edit|Write) 훅: omp/ 아래 설정을 고치면 라이브 ~/.omp/agent 와 어긋난다는 걸 알린다.
# 자동으로 복사하지는 않는다 - config.yml은 omp 자신의 상태가 섞여 있어 사람이 확인해야 한다.
f=$(python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
case "$f" in
  */omp/models.yml|*/omp/config.fragment.yml)
    live="$(omp config path 2>/dev/null | tail -1)"; [[ -n "$live" ]] || live="$HOME/.omp/agent"
    echo "omp 설정이 바뀌었다. 라이브($live)에 반영할 것: models.yml은 cp, config.yml은 modelRoles만 손으로. 끝나면 /v1 nothink 스모크 테스트." ;;
  */ollama/Modelfile.*)
    n=$(basename "$f" | sed 's/^Modelfile\.//')
    echo "Modelfile이 바뀌었다. 'ollama create $n -f $f' 로 다시 만들어야 반영된다." ;;
esac
exit 0
