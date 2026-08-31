#!/bin/bash
# oMLX 설치·설정 동기화 스크립트.
# ollama/install.sh 와 같은 역할을 oMLX 쪽에서 한다:
#  - brew tap jundot/omlx 에서 oMLX 설치 (Qwen3.5/3.6 가속 커널 포함)
#  - 모델 3개를 HF 캐시로 다운로드 (oMLX 는 ~/.cache/huggingface/hub 를 자동 발견한다)
#  - 이 디렉터리의 model_settings.json / model_profiles.json 을 ~/.omlx/ 에 설치
#  - GPU wired 한도(iogpu.wired_limit_mb)를 RAM 티어에 맞춰 부팅 지속으로 설정(sudo)
#  - 서비스 잔재(brew services, 예전 LaunchAgent) 정리 후 앱만 실행(서버 기동은 사용자가 메뉴바 Start)
#
# 전역 ~/.omlx/settings.json 은 여기서 관리하지 않는다 - oMLX 가 자기 값(auth
# secret_key 등)을 함께 저장하는 파일이라 커밋 대상이 아니다. 우리가 정하는 것은
# 모델 단위 파일 2개뿐이다.
#
# 주의: 본체 다운로드가 23.1GiB 다. wired 한도 설정과 다운로드는 sudo·대용량이라
# 사용자가 직접 실행한다.
set -euo pipefail
cd "$(dirname "$0")"

if ! brew list omlx >/dev/null 2>&1; then
  # --with-custom-kernel: Qwen3.5/3.6(우리 코더·aux 둘 다) 네이티브 커널 가속
  brew install jundot/omlx/omlx --with-custom-kernel
fi

HF=/opt/homebrew/opt/omlx/libexec/bin/hf
# 4bit(+MTP-4bit)는 2026-08-27 기각·캐시 삭제 — 웜 70.2 tok/s 로 5bit 동급 이하, 45m TO+회귀 1(bench/2026-08-27.s2.coder-4bit.md)
# 모든 모델은 oMLX 앱 다운로드로 관리한다(~/.omlx/models, 짧은 서빙 id — 2026-08-28 전면 포팅,
# HF 캐시 제거·hf CLI 경로 폐지, 다운로드는 POST /admin/api/hf/download). 관리 대상:
# Qwen3.6-35B-A3B-5bit + Qwen3.6-35B-A3B-MTP-5bit(드래프터), Qwen3.5-4B-4bit + Qwen3.5-4B-MTP-4bit(aux),
# Qwen3.8-27B-4bit(선택 코더, 2026-08-31 사용자 요청으로 재등록 — 드래프터 없음, 15GB),
# gemma-4-26b-a4b-it-5bit(선택 코더, 2026-08-31 — MoE 26B/활성 4B, 18GB, 드래프터 없음).
# **`-it` 판이어야 한다**: 베이스 `gemma-4-26b-a4b-5bit`(+4bit)는 대화 형식·stop 토큰이 없어
# 프롬프트를 되풀이한다(실측 2026-08-31). 그래서 베이스 두 벌(5bit 17GB + 4bit 15GB)은
# 같은 날 스토어에서 삭제했다 — `DELETE /admin/api/hf/models/<id>`.
#
# 서빙 목록에서 숨긴 것들(`is_hidden: true`, 2026-08-31) — omp 가 discovery 로 `/v1/models` 를
# 그대로 읽으므로, 채팅으로 부를 수 없는 것은 서버가 아예 안 내보내게 한다:
#   Qwen3.6-35B-A3B-MTP-5bit, Qwen3.5-4B-MTP-4bit  - MTP 드래프터(단독 호출 대상 아님)
#   Qwen3.6-35B-A3B-DFlash, Qwen3.8-27B-DFlash2    - DFlash 사이드카
# 숨김은 파일에 직접 써 넣으면 앱이 무시한다 - `PUT /admin/api/models/<id>/settings` 로 적용한다.
# 9B·3.8 실험 모델은 2026-08-28 어드바이저 매트릭스 기각과 함께 삭제(bench/2026-08-28.s2.advmatrix.md).
# 9B 코더·3.8 어드바이저(+각 MTP 드래프터)는 oMLX 앱 다운로드로 관리한다(~/.omlx/models,
# 서빙 id 는 짧은 형식 "Qwen3.5-9B-MLX-4bit"/"Qwen3.8-27B-nvfp4"). HF 캐시 중복은 2026-08-28
# 제거(21GB 회수). 앱 없이 재현하려면 hf download 후 model_settings/models.yml 의 id 를
# mlx-community-- 형식으로 되돌린다.
# 2026-08-25 배제·캐시 삭제한 실험 모델들은 다운로드하지 않는다(근거는 bench/ 기록):
#  - 로스터 비-Qwen 5모델(Gemma×3·Devstral·Qwen3-Coder-30B): 양쪽 게이트 초록 실패(roster.md)
#  - GLM-4.7-Flash-4bit: integration 타임아웃 FAIL(3.6 대비 느림)
#  - Qwen3.8 dense 27B(nvfp4·oQ6·표준4bit): 전부 writes 0(에이전트 루프에서 파일 미생성, 양자화 무관)
# 재검증하려면 해당 $HF download 줄과 model_settings.json/model_profiles.json/models.yml 등록을 되살린다.

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
d['server']['auto_start_on_launch'] = False   # 자동 시작 끔 - 서버는 앱 메뉴바 Start 로만 띄운다(omlx start=brew services=금지)
d.setdefault('memory', {})['memory_guard_tier'] = 'safe'
import subprocess
_ram_gb = int(subprocess.run(['sysctl','-n','hw.memsize'], capture_output=True, text=True).stdout.strip() or 0) // (1024**3)
# RAM 티어: 64GB+ 는 8GB(앱 기본값과 같음), 48GB 는 4GB — 모델 23GB + KV ~10GB 위에
# 8GB 를 더 얹으면 48GB 티어의 wired_limit_mb(40GB)를 넘는다.
d.setdefault('cache', {})['hot_cache_max_size'] = '8GB' if _ram_gb >= 60 else '4GB'
# 벤치 러너(skill://llm-bench)가 셀마다 admin API(/admin/api/models/<id>/unload)로 로드된 모델을 비워
# 강제 단일 상주를 만든다. 루프백 무인증 admin 접근을 위해 skip_api_key_verification 을 켠다(127.0.0.1 전용).
d.setdefault('auth', {})['skip_api_key_verification'] = True
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)
print('oMLX port ->', d['server']['port'], '| auto_start_on_launch ->', d['server']['auto_start_on_launch'],
      '| memory_guard_tier ->', d['memory']['memory_guard_tier'], '| hot_cache_max_size ->', d['cache']['hot_cache_max_size'])
PY

# --- GPU wired 한도 (RAM 티어별, 부팅 지속) ----------------------------------------
# macOS 는 GPU 가 고정(wired)할 수 있는 메모리를 RAM 의 ~75% 로 막는다(48GB→~36GB, 64GB→~48GB).
# 코더(로드 23GB, 창이 차면 +~10GB)와 aux(4B ~5GB)가 이 한도를 넘으면 레이어가 CPU 로 내려가
# 속도가 급락한다. RAM 티어에 맞춰 올린다 — 48·64GB 는 RAM-8GB(memory_guard_tier 'safe' 와 같은
# 값이라 admin 배너도 안 뜬다), 96GB+ 는 RAM-12GB, 48GB 미만은 35B 가 어차피 안 들어가 기본값
# 유지. macOS 는 부팅 시 /etc/sysctl.conf 를 읽으므로 거기에 idempotent 하게 써 재부팅에도 유지하고
# 즉시 반영까지 한다. sudo 가 필요하고, 거부하면 수동 명령만 안내하고 계속 진행한다.
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if   (( RAM_GB >= 96 )); then WIRED_MB=$(( (RAM_GB - 12) * 1024 ))
elif (( RAM_GB >= 48 )); then WIRED_MB=$(( (RAM_GB - 8) * 1024 ))   # 48GB→40960, 64GB→57344
else WIRED_MB=0; fi
SYSCTL_CONF=/etc/sysctl.conf
if (( WIRED_MB > 0 )); then
  CUR="$(sysctl -n iogpu.wired_limit_mb 2>/dev/null || echo 0)"
  if [[ "$CUR" != "$WIRED_MB" ]] || ! grep -qxF "iogpu.wired_limit_mb=$WIRED_MB" "$SYSCTL_CONF" 2>/dev/null; then
    echo "gpu: iogpu.wired_limit_mb $CUR -> $WIRED_MB (${RAM_GB}GB 호스트, sudo 필요)"
    if sudo -n true 2>/dev/null || sudo -v; then
      sudo sysctl -w "iogpu.wired_limit_mb=$WIRED_MB" >/dev/null              # 즉시 반영
      sudo touch "$SYSCTL_CONF"                                               # 부팅 지속
      if grep -q '^iogpu.wired_limit_mb=' "$SYSCTL_CONF"; then
        sudo sed -i '' "s/^iogpu.wired_limit_mb=.*/iogpu.wired_limit_mb=$WIRED_MB/" "$SYSCTL_CONF"
      else
        echo "iogpu.wired_limit_mb=$WIRED_MB" | sudo tee -a "$SYSCTL_CONF" >/dev/null
      fi
      echo "gpu: 영구 적용 ($SYSCTL_CONF)"
    else
      echo "gpu: sudo 거부 - 한도를 올리지 못했다. 수동: sudo sysctl -w iogpu.wired_limit_mb=$WIRED_MB" >&2
    fi
  else
    echo "gpu: iogpu.wired_limit_mb=$WIRED_MB (이미 적용됨)"
  fi
else
  echo "gpu: ${RAM_GB}GB 호스트 - wired limit 기본값 유지(35B 미적재 티어)"
fi

# --- 서버 = GUI 앱 (DMG) -----------------------------------------------------------
# 서버는 /Applications/oMLX.app 이 관리한다(메뉴바 Start/Stop). **`omlx start|restart` 는 쓰지 않는다** —
# 실측(2026-08-25)상 그건 brew services(homebrew.mxcl.omlx) 또는 별도 headless 서버라, 앱 서버와 포트
# 9090 을 두고 충돌하고 규칙 6(자동 재시작) 위반이다(pre-bash 훅도 deny). brew 포뮬러는 hf CLI 용으로만 쓴다.
# brew services(homebrew.mxcl.omlx, KeepAlive)와 예전 LaunchAgent(com.local-llm.omlx) 잔재는 걷어낸다.
if brew services list 2>/dev/null | grep -qE '^omlx\s+(started|scheduled|error)'; then
  brew services stop jundot/omlx/omlx
fi
rm -f "$HOME/Library/LaunchAgents/homebrew.mxcl.omlx.plist"
launchctl bootout "gui/$(id -u)/com.local-llm.omlx" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.local-llm.omlx.plist"
if [[ ! -d /Applications/oMLX.app ]]; then
  echo "oMLX.app 이 없다 - https://github.com/jundot/omlx/releases 의 .dmg 를 /Applications 에 설치한 뒤 다시 실행할 것" >&2
  exit 1
fi
# 서버는 **앱 메뉴바 Start 로만** 띄운다. `omlx start|restart`(실측 2026-08-25: brew services
# homebrew.mxcl.omlx 를 조작하거나 별도 headless 서버를 띄운다)는 규칙 6 위반이고 앱 서버와 포트
# 9090 을 두고 충돌하므로 여기서 쓰지 않는다(pre-bash 훅도 deny). 앱만 실행해 두고 사용자가 Start.
open -a oMLX 2>/dev/null || true
echo "oMLX.app 을 열었다. **메뉴바 아이콘 > Start** 로 서버를 9090 에 올린 뒤 아래가 200 이 될 때까지 기다린다."
for _ in $(seq 1 120); do
  curl -sf http://127.0.0.1:9090/v1/models >/dev/null && { echo "oMLX 준비 완료 - http://127.0.0.1:9090/v1 (관리판 /admin, 서버는 앱이 관리)"; break; }
  sleep 2
done
