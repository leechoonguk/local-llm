#!/usr/bin/env bash
# oMLX 스모크 — 설정을 베이크한 뒤 "정말 먹었는지"를 실제 종료코드로 확인한다.
# 교훈 반영(2026-08-28):
#   - 재시작 성공 여부는 셔틀 메시지가 아니라 uptime 으로 본다(셔틀은 실패 문구를 내고도 서버는 살아 있었다).
#   - think 모델 스모크는 max_tokens >= 1000 으로 — 절단되면 reasoning 분리가 안 된 것처럼 보인다(오탐 실측).
#   - 설정 키는 서버가 인정해야 의미가 있다(무효 키를 조용히 버린다) — admin API 로 되읽어 확인한다.
#   - MTP 발화는 서버 로그의 vlm_mtp stats 로만 확인된다(응답 본문에는 흔적이 없다).
# 사용: bash omlx/smoke.sh [모델id]   (기본값: 기본 코더 프로파일)
set -uo pipefail

URL=${OMLX_URL:-http://127.0.0.1:9090}
MODEL=${1:-Qwen3.6-35B-A3B-5bit:mtp}
BASE=${MODEL%%:*}
LOG="$HOME/.omlx/logs/server.log"

curl -sf "$URL/v1/models" >/dev/null || { echo "FAIL: $URL 미가동 — oMLX.app 으로 서버를 올린다"; exit 1; }
echo "서빙: $(curl -s "$URL/v1/models" | python3 -c 'import json,sys; print(", ".join(m["id"] for m in json.load(sys.stdin)["data"]))')"

PID=$(lsof -nP -iTCP:9090 -sTCP:LISTEN -t 2>/dev/null | head -1)
[ -n "$PID" ] && echo "uptime: $(ps -o etime= -p "$PID" | tr -d ' ')"

BEFORE=$(grep -c "vlm_mtp stats" "$LOG" 2>/dev/null || echo 0)

RESP=$(curl -s "$URL/v1/chat/completions" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Explain in two sentences why binary search is O(log n).\"}],\"max_tokens\":2000}")
echo "$RESP" | python3 -c '
import json, sys
try:
    m = json.load(sys.stdin)["choices"][0]["message"]
except Exception as e:
    print(f"FAIL: 응답 파싱 불가 ({e})"); sys.exit(1)
c = (m.get("content") or "").strip()
r = (m.get("reasoning") or m.get("reasoning_content") or "")
if not c:
    print("FAIL: content 가 비었다 — 모델 id·프로파일 확인"); sys.exit(1)
print(f"  응답 {len(c)}자 | reasoning {len(r)}자(분리 {bool(r)})")
' || exit 1

AFTER=$(grep -c "vlm_mtp stats" "$LOG" 2>/dev/null || echo 0)
if [ "$AFTER" -gt "$BEFORE" ]; then
  echo "  MTP 발화 ✓ $(grep 'vlm_mtp stats' "$LOG" | tail -1 | grep -o 'accepted=[0-9/]* ([0-9.]*%)')"
else
  echo "  MTP 미발화 — thinking_budget 이 걸려 있으면 정상이다(레벨 무관, 2026-08-28 확정: 63.7 vs 75.8 tok/s)."
  echo "             budget 을 안 쓰는데도 스킵이면 vlm_mtp_enabled·드래프터 페어링·비중립 penalty 를 확인한다."
fi

curl -s "$URL/admin/api/models" | python3 -c "
import json, sys
raw = json.load(sys.stdin)
items = raw if isinstance(raw, list) else raw.get('models', raw.get('data', []))
for m in items:
    if str(m.get('id') or m.get('name')) == '$BASE':
        s = m.get('settings', m)
        print('  서버가 보는 값:', {k: v for k, v in s.items() if 'think' in k.lower() or k in ('max_context_window', 'max_tokens')})
        break
else:
    print('  경고: admin API 에서 $BASE 를 못 찾았다')
"
echo "smoke OK"
