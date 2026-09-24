#!/bin/bash
# GPU wired 한도(iogpu.wired_limit_mb)를 "oMLX 를 띄울 때만" 올리는 단일 진실 (2026-09-24).
#
# 배경: 이 sysctl 은 메모리를 쓰는 값이 아니라 GPU 가 고정(wired)할 수 있는 상한(캡)이다. 올려 둬도
# 비용이 없고 재부팅하면 커널 기본값(RAM 의 ~75%)으로 돌아간다. 그래서 부팅 지속(/etc/sysctl.conf —
# macOS 가 실제로 처리하는지 불확실, 2026-09-24 재부팅 후 값이 0 이었다)이 아니라 **서버를 띄우는 관문
# (omlx/ensure-app-server.sh)이 매번 확인하고 올리는** 구조로 바꿨다. 다른 스펙의 머신에서도 값을
# 고정하지 않고 hw.memsize 로 계산한다(oMLX memory_guard_tier 'safe' = RAM−8GB 와 같은 식).
#
# 설치(1회, sudo — 사용자 몫, `omlx/install.sh` 가 한다):
#   /usr/local/sbin/omlx-wired-limit  ← 이 파일의 root 소유(0755) 사본
#   /etc/sudoers.d/omlx-wired-limit   ← "%admin ALL=(root) NOPASSWD: /usr/local/sbin/omlx-wired-limit"
#   sudoers 가 여는 것은 임의 sysctl 이 아니라 이 고정 경로의 up/down 뿐이다. 사본이 root 소유·비쓰기여야
#   사용자 권한으로 내용을 바꿔 root 로 실행시키는 구멍이 없다 — install.sh 가 chown root:wheel 을 건다.
#
# 사용:
#   bash omlx/wired-limit.sh tier     # 이 머신의 목표값(MiB)을 출력한다. 0 = 기본값 유지 티어. root 불필요
#   bash omlx/wired-limit.sh status   # 현재값/목표값/일치 여부. root 불필요
#   sudo -n /usr/local/sbin/omlx-wired-limit up    # 목표값으로 올린다(이미 같으면 no-op). 관문이 부른다
#   sudo -n /usr/local/sbin/omlx-wired-limit down  # 0 = 커널 기본값으로 되돌린다(선택 — 캡이라 안 내려도 손해 없음)
#
# 티어(CLAUDE.md "환경 사실"·install.sh 와 같은 규칙): 48·64GB → RAM−8GB(40960/57344), 96GB+ → RAM−12GB,
# 48GB 미만 → 0(35B 가 어차피 안 들어가는 티어 — 기본값 유지).
set -u
PATH=/usr/sbin:/usr/bin:/bin
SYSCTL=/usr/sbin/sysctl
KEY=iogpu.wired_limit_mb

ram_gb() { echo $(( $($SYSCTL -n hw.memsize) / 1073741824 )); }
tier_mb() {
  local gb; gb=$(ram_gb)
  if   (( gb >= 96 )); then echo $(( (gb - 12) * 1024 ))
  elif (( gb >= 48 )); then echo $(( (gb - 8) * 1024 ))
  else echo 0; fi
}
current_mb() { $SYSCTL -n $KEY 2>/dev/null || echo 0; }

case "${1:-status}" in
  tier)   tier_mb ;;
  status)
    want=$(tier_mb); cur=$(current_mb)
    if (( want == 0 )); then echo "wired: $(ram_gb)GB 호스트 — 기본값 유지 티어(현재 ${cur})"; exit 0; fi
    if [[ "$cur" == "$want" ]]; then echo "wired: ${cur} = 목표 ${want} (OK)"; exit 0; fi
    echo "wired: 현재 ${cur}, 목표 ${want} — 관문(ensure-app-server.sh)이 올린다. 설치 안 됐으면 omlx/install.sh"; exit 1 ;;
  up)
    [[ $(id -u) -eq 0 ]] || { echo "up 은 root 로 실행한다(sudo -n /usr/local/sbin/omlx-wired-limit up)" >&2; exit 2; }
    want=$(tier_mb); cur=$(current_mb)
    if (( want == 0 )); then echo "wired: 기본값 유지 티어 — 변경 없음"; exit 0; fi
    if [[ "$cur" == "$want" ]]; then echo "wired: ${want} 이미 적용"; exit 0; fi
    $SYSCTL -w "$KEY=$want" >/dev/null && echo "wired: ${cur} -> ${want}" ;;
  down)
    [[ $(id -u) -eq 0 ]] || { echo "down 은 root 로 실행한다(sudo -n /usr/local/sbin/omlx-wired-limit down)" >&2; exit 2; }
    $SYSCTL -w "$KEY=0" >/dev/null && echo "wired: 커널 기본값으로 복귀(0)" ;;
  *) echo "usage: $0 tier|status|up|down" >&2; exit 2 ;;
esac
