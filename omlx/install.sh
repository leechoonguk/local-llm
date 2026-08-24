#!/bin/bash
# oMLX 설치·설정 동기화 스크립트.
# ollama/install.sh 와 같은 역할을 oMLX 쪽에서 한다:
#  - brew tap jundot/omlx 에서 oMLX 설치 (Qwen3.5/3.6 가속 커널 포함)
#  - 모델 3개를 HF 캐시로 다운로드 (oMLX 는 ~/.cache/huggingface/hub 를 자동 발견한다)
#  - 이 디렉터리의 model_settings.json / model_profiles.json 을 ~/.omlx/ 에 설치
#  - 서비스 재시작
#
# 전역 ~/.omlx/settings.json 은 여기서 관리하지 않는다 - oMLX 가 자기 값(auth
# secret_key 등)을 함께 저장하는 파일이라 커밋 대상이 아니다. 우리가 정하는 것은
# 모델 단위 파일 2개뿐이다.
#
# 주의: 본체 다운로드가 23.1GiB 다. GPU wired 한도(iogpu.wired_limit_mb)는
# sudo 가 필요하므로 여기서 만지지 않는다 - README "설치 / 재현" 참고.
set -euo pipefail
cd "$(dirname "$0")"

if ! brew list omlx >/dev/null 2>&1; then
  # --with-custom-kernel: Qwen3.5/3.6(우리 코더·aux 둘 다) 네이티브 커널 가속
  brew install jundot/omlx/omlx --with-custom-kernel
fi

HF=/opt/homebrew/opt/omlx/libexec/bin/hf
$HF download mlx-community/Qwen3.6-35B-A3B-5bit        # 코더 본체 23.1GiB
$HF download mlx-community/Qwen3.6-35B-A3B-MTP-5bit    # MTP 드래프터 0.6GiB
$HF download mlx-community/Qwen3.5-4B-4bit             # aux(tiny 역할) 2.3GiB
$HF download mlx-community/Qwen3.8-27B-oQ6             # 무거운 추론용 dense 27B, 21.7GiB
$HF download mlx-community/Qwen3.8-27B-MTP-8bit        # 3.8 MTP 드래프터 0.4GiB
$HF download mlx-community/Qwen3.8-27B-nvfp4           # oQ6 속도 비교용 4bit, 15.0GiB
$HF download mlx-community/Qwen3.8-27B-MTP-nvfp4       # 3.8 nvfp4 MTP 드래프터 0.25GiB

mkdir -p ~/.omlx
cp model_settings.json ~/.omlx/model_settings.json
cp model_profiles.json ~/.omlx/model_profiles.json

# 포트 9090 강제 - 8000 은 개발 서버(FastAPI 등)와 충돌이 잦다.
# memory_guard_tier 는 "safe"(RAM-8GB 정적 상한) 로 강제한다 - "balanced"(RAM-6GB)의
# 정적 상한이 이 레포가 sysctl로 거는 iogpu.wired_limit_mb 보다 커서(64GB: 58GB > 56GB,
# 48GB: 42GB > 40GB - CLAUDE.md 표 참고) admin 대시보드가 계속 "sysctl 더 올리라"는
# 배너를 띄운다. 실사용 상한(min(static, dynamic, metal_cap))은 metal_cap 이 커널 캡을
# 접어 넣어 실제로는 항상 안전했지만(2026-08-24 소스 확인), 커널 캡을 더 올리는 대신
# oMLX 쪽 목표를 캡 아래로 낮추는 게 48GB 맥으로 옮겨도 깨지지 않는다 - "safe" 의 8GB
# 예약은 이 레포의 두 RAM 티어 모두에서 정확히 RAM-8GB = 우리가 건 wired_limit_mb 와
# 같아진다. settings.json 은 oMLX 가 자기 값(auth secret 등)도 함께 저장하므로 필요한
# 키만 patch 한다.
#
# hot_cache_max_size 는 기본값이 "0"(끔)이다 - 실측(2026-08-24): SSD paged cache(디폴트
# 경로 ~/.omlx/cache, 켜져 있음)는 유지하되, 그 앞단 인메모리 레이어가 없어 반복
# prefix 마다 SSD 왕복이 붙는다. 4GB 로 켠다. ssd_cache_dir 는 명시하지 않는다 -
# 미지정이면 서버가 ~/.omlx/cache 를 기본으로 쓰는데, 여기서 명시하면 재설치할 때마다
# 다른 이름을 주는 실수 하나로 이미 데워진 캐시가 고아가 된다(실측: 이 세션에서 한 번
# 그렇게 15.55GB 를 날릴 뻔했다) - 코드가 정하는 기본값을 신뢰하는 게 더 안전하다.
python3 - <<'PY'
import json, os
p = os.path.expanduser('~/.omlx/settings.json')
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault('server', {})['port'] = 9090
d['server']['auto_start_on_launch'] = False   # 자동 시작 끔 - 서버는 아래 LaunchAgent 를 손으로 kickstart 한다
d.setdefault('memory', {})['memory_guard_tier'] = 'safe'
d.setdefault('cache', {})['hot_cache_max_size'] = '4GB'
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)
print('oMLX port ->', d['server']['port'], '| auto_start_on_launch ->', d['server']['auto_start_on_launch'],
      '| memory_guard_tier ->', d['memory']['memory_guard_tier'], '| hot_cache_max_size ->', d['cache']['hot_cache_max_size'])
PY

# --- LaunchAgent (자동 시작·재시작 꺼짐) ----------------------------------------
# brew services 의 homebrew.mxcl.omlx 는 KeepAlive/RunAtLoad 가 true 라 로그인 시 뜨고 죽으면 되살아난다.
# 벤치는 단일 상주·명시적 기동이 전제이므로 그 서비스는 내리고, 레포의 plist(둘 다 false)로 대체한다.
# 기동: launchctl kickstart -k gui/$UID/com.local-llm.omlx / 중지: launchctl kill TERM gui/$UID/com.local-llm.omlx
LABEL=com.local-llm.omlx
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if brew services list 2>/dev/null | grep -qE '^omlx\s+(started|scheduled|error)'; then
  brew services stop jundot/omlx/omlx
fi
rm -f "$HOME/Library/LaunchAgents/homebrew.mxcl.omlx.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/omlx"
OMLX_BIN="$(brew --prefix omlx)/bin/omlx"
sed -e "s|__HOME__|$HOME|g" -e "s|__OMLX_BIN__|$OMLX_BIN|g" "$LABEL.plist.template" > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart "gui/$(id -u)/$LABEL"
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:9090/v1/models >/dev/null && break
  sleep 1
done
echo "oMLX 준비 완료 - http://127.0.0.1:9090/v1 (관리판: http://localhost:9090/admin, 로그: ~/Library/Logs/omlx/omlx.log)"
