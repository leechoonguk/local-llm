#!/bin/bash
# oMLX 서버의 "앱 소유" 를 보장하는 정본 관문 (2026-09-01).
#
# 실측 근거: 셔틀 `omlx restart` 가 앱 밖의 고아 서버(PPID 1)를 만들었고, 다음 날 앱이
# 재기동돼도 그 고아가 계속 서빙했다. 측정·운영의 기준은 "oMLX.app 이 관리하는 서버"다 —
# 모델 다운로드·베이크·스모크·벤치 셀 등 oMLX 를 만지는 모든 플로우는 이 스크립트를 먼저 통과한다.
#
# 사용: bash omlx/ensure-app-server.sh [--restart]
#   (없음)    — 살아 있고 앱 소유면 통과. 아니면 1회 자동 교정(고아 stop → 앱 확인 → start) 후 재판정.
#   --restart — 설정 반영용: 무조건 stop 후 앱 소유로 재기동을 보장한다.
# 종료코드: 0 = 앱 소유 서버 가동 / 1 = 실패(메뉴바 Start 필요 — 사용자 액션)
set -u
URL="http://127.0.0.1:9090"
SHUTTLE="$HOME/.omlx/bin/omlx"

alive() { [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$URL/v1/models")" = "200" ]; }
app_managed() {
  local pid hop cmd
  pid=$(pgrep -f omlx-server | head -1)
  for hop in 1 2 3 4 5 6 7 8; do
    [ -z "$pid" ] || [ "$pid" = "0" ] || [ "$pid" = "1" ] && return 1
    cmd=$(ps -o command= -p "$pid" 2>/dev/null)
    case "$cmd" in */oMLX.app/Contents/MacOS/oMLX*) return 0;; esac
    pid=$(ps -o ppid= -p "$pid" | tr -d ' ')
  done
  return 1
}

if [ "${1:-}" != "--restart" ] && alive && app_managed; then
  echo "omlx: 앱 소유 서버 가동 중 (uptime $(curl -s --max-time 3 $URL/api/status | /usr/bin/sed -n 's/.*uptime_seconds":\([0-9]*\).*/\1/p')s)"
  exit 0
fi

echo "omlx: 교정 — 서버·앱 재시작(auto_start_on_launch=true 로 앱이 자식 서버를 띄운다)"
"$SHUTTLE" stop >/dev/null 2>&1; sleep 1
pkill -f omlx-server 2>/dev/null; sleep 1   # 셔틀이 모르는 고아까지(실측: stop 이 못 잡은 고아 1건)
APP_PID=$(pgrep -f "oMLX.app/Contents/MacOS/oMLX" | head -1)
[ -n "$APP_PID" ] && { kill -TERM "$APP_PID" 2>/dev/null; sleep 3; }
open -a oMLX
for _ in $(seq 1 20); do alive && break; sleep 2; done

alive || { echo "omlx: 서버가 :9090 에 안 뜬다 — oMLX.app 메뉴바에서 Start 후 재실행" >&2; exit 1; }
if ! app_managed; then
  echo "omlx: 서버가 여전히 앱 소유가 아니다 — ~/.omlx/settings.json 의 server.auto_start_on_launch 가 true 인지 확인하고(check-autostart 가 검사), 앱을 재시작하라." >&2
  exit 1
fi
echo "omlx: 앱 소유 서버 가동(검증 완료)"
