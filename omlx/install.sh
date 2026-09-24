#!/bin/bash
# oMLX 설치·설정 동기화 스크립트.
# ollama/install.sh 와 같은 역할을 oMLX 쪽에서 한다:
#  - 서버는 GUI 앱(/Applications/oMLX.app, DMG)이다 — brew 포뮬러·jundot/omlx 탭은 2026-08-27 폐지, 여기서 설치하지 않는다
#    (앱이 없으면 아래에서 안내하고 멈춘다). 모델은 앱 스토어(~/.omlx/models)에서 admin API 로 관리
#  - 이 디렉터리의 model_settings.json / model_profiles.json 을 ~/.omlx/ 에 설치
#  - GPU wired 캡 래퍼(omlx/wired-limit.sh 의 root 사본 + sudoers) 설치 — 값은 관문이 띄울 때 올린다(sudo 1회)
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

# 2026-09-24: 옛 `brew install jundot/omlx/omlx --with-custom-kernel` 블록 제거 — 탭·포뮬러가 사라져 brew 가
# "invalid option" 으로 죽으면서 set -e 가 스크립트 전체를 중단시켰다(실측). 앱 유무만 확인한다.
if [[ ! -d /Applications/oMLX.app ]]; then
  echo "oMLX.app 이 없다 — https://github.com/jundot/omlx/releases 의 DMG(macos26-27) 를 /Applications 에 설치한 뒤 다시 실행" >&2
  exit 1
fi
# 4bit(+MTP-4bit)는 2026-08-27 기각·캐시 삭제 — 웜 70.2 tok/s 로 5bit 동급 이하, 45m TO+회귀 1(bench/2026-08-27.s2.coder-4bit.md)
# 모든 모델은 oMLX 앱 다운로드로 관리한다(~/.omlx/models, 짧은 서빙 id — 2026-08-28 전면 포팅,
# HF 캐시 제거·hf CLI 경로 폐지, 다운로드는 POST /admin/api/hf/download). 관리 대상:
# Qwen3.6-35B-A3B-5bit(코더, 드래프터 없음), Qwen3.5-4B-4bit + Qwen3.5-4B-MTP-4bit(aux — MTP 실동 45.3 tok/s),
# 2026-09-24 스토어 정리(사용자 결정, DELETE /admin/api/hf/models/<id>): Qwen3.8-27B-4bit(15GB)+MTP-4bit+DFlash2 —
#   dense 27B 는 M4 Pro 에서 디코드 15 tok/s 상한(bench/2026-09-24.s1.k2-horizon.md), gemma-4-26b-a4b-it-5bit(17GB) —
#   8/25 로스터 파괴적·이후 미사용, Qwen3.6-35B-A3B-MTP-5bit·Qwen3.6-35B-A3B-DFlash — MTP 계열 전부 재기각(같은 기록 13~21행),
#   Jundot/Qwen3.6-35B-A3B-oQ4e-mtp(20GB, 네이티브 MTP 실험용·레포 미등록) — 순손실 −19%.
# K2-Horizon-MoVA-36B-A4B-oQ4e(후보였다가 **같은 날 기각·삭제** — 32k 생성 15.1 tok/s, MoVA 긴 컨텍스트 비용. MBZUAI IFM 9/3 공개, MoE 36B/활성 4B, oQ4e 21GB.
#   oMLX 0.7.0.dev1+ 가 k2_horizon 을 네이티브 지원(reasoning·tool 파서는 model_type 으로 자동 선택, reasoning_parser 키 불필요)).
#   mlx-community oQ4e 는 그대로는 안 올라간다(2026-09-24 실측): 전문가 키가 `mlp.switch_mlp.*`(리포 동봉 모듈 이름)라
#   내장 모듈(`mlp.experts.*`)과 어긋나고, `self_attn.v_router` 가 4~5bit 로 양자화돼 있어 "routers require BF16" 으로
#   죽는다. `trust_remote_code` 로 동봉 모듈을 돌리는 대신 파일을 고쳤다 — 앱 인터프리터(~/.omlx/bin/omlx-cluster-python)로
#   (1) 샤드 5개의 switch_mlp 키를 experts 로 리네임 + 인덱스 갱신, (2) v_router weight/scales/biases 를 mx.dequantize 로
#   BF16 복원 + config quantization 의 해당 경로를 false 로 — `omlx/fix-k2-horizon-checkpoint.py`(멱등). 재다운로드하면 다시 돌린다.
# Gemma 를 되살린다면 **`-it` 판이어야 한다**: 베이스 `gemma-4-26b-a4b-5bit`(+4bit)는 대화 형식·stop 토큰이 없어
# 프롬프트를 되풀이한다(실측 2026-08-31).
#
# 서빙 목록에서 숨긴 것(`is_hidden: true`) — omp 가 discovery 로 `/v1/models` 를 그대로 읽으므로,
# 채팅으로 부를 수 없는 것은 서버가 아예 안 내보내게 한다:
#   Qwen3.5-4B-MTP-4bit  - aux MTP 드래프터(단독 호출 대상 아님)
#   (0.7.0.dev4 는 z-lab/… 처럼 org 가 다른 스토어 항목을 `z-lab--<name>` id 로 내보낸다 — 숨김 키가 짧은 이름이면 안 맞아 노출됐다, 2026-09-24 실측. 해당 사이드카는 삭제)
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
d['server']['auto_start_on_launch'] = True    # 서버 수명=앱 수명(2026-09-01 반전) - 셔틀 start 는 고아를 띄우므로 앱 재시작이 앱 자식 서버의 유일 경로다. 로그인 자동 기동(로그인 항목)은 여전히 금지
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

# --- GPU wired 한도: "띄울 때 올리는" 래퍼 설치 (2026-09-24 개정) ---------------------
# macOS 는 GPU 가 고정(wired)할 수 있는 메모리를 RAM 의 ~75% 로 막는다(48GB→~36GB, 64GB→~48GB).
# 이 값은 캡이라 올려 둬도 비용이 없고 재부팅하면 기본값으로 돌아간다. 예전의 /etc/sysctl.conf 부팅
# 지속은 걷어냈다 — macOS 가 그 파일을 처리한다는 보장이 없고(2026-09-24 재부팅 후 0), "LLM 을 돌릴 때만
# 올린다"는 의도와도 어긋난다. 대신 `omlx/wired-limit.sh`(티어 계산 = 단일 진실)를 root 소유 사본으로
# 설치하고, sudoers 로 그 고정 경로만 비밀번호 없이 허용한다. 관문 `omlx/ensure-app-server.sh` 가 서버를
# 띄울 때마다 `sudo -n /usr/local/sbin/omlx-wired-limit up` 을 불러 이 머신의 티어 값으로 올린다.
# 다른 스펙의 PC 에서도 같은 설치 1회로 끝난다(값은 hw.memsize 로 계산). sudo 가 필요하고, 거부하면
# 안내만 하고 계속 진행한다(서버는 기본 캡으로 동작 — `make check-live-sync` 가 드리프트로 잡는다).
WL_SRC="$PWD/wired-limit.sh"   # 17행에서 이미 스크립트 디렉터리로 cd 했다(상대 $0 재해석 금지 — 2026-09-24 실측 버그)
WL_BIN=/usr/local/sbin/omlx-wired-limit
WL_SUDOERS=/etc/sudoers.d/omlx-wired-limit
WL_RULE='%admin ALL=(root) NOPASSWD: /usr/local/sbin/omlx-wired-limit'
WIRED_MB=$(bash "$WL_SRC" tier)
if [[ -x "$WL_BIN" ]] && cmp -s "$WL_SRC" "$WL_BIN" && sudo -n "$WL_BIN" tier >/dev/null 2>&1; then   # tier 는 항상 exit 0 — sudoers 유무만 본다
  echo "gpu: 래퍼 설치됨($WL_BIN, sudoers OK) — $(bash "$WL_SRC" status)"
else
  echo "gpu: 래퍼 설치/갱신 (sudo 필요) — $WL_BIN + $WL_SUDOERS"
  if sudo -n true 2>/dev/null || sudo -v; then
    sudo install -d -o root -g wheel -m 755 /usr/local/sbin
    sudo install -o root -g wheel -m 755 "$WL_SRC" "$WL_BIN"
    echo "$WL_RULE" | sudo tee "$WL_SUDOERS" >/dev/null && sudo chmod 440 "$WL_SUDOERS"
    if sudo visudo -cf "$WL_SUDOERS" >/dev/null; then
      echo "gpu: sudoers 검증 OK"
    else
      sudo rm -f "$WL_SUDOERS"; echo "gpu: sudoers 문법 실패 — 파일 제거" >&2
    fi
  else
    echo "gpu: sudo 거부 — 래퍼 미설치. 서버는 기본 캡으로 돈다(목표 ${WIRED_MB}MiB). 수동 설치는 omlx/wired-limit.sh 상단 주석" >&2
  fi
fi
if (( WIRED_MB > 0 )); then
  sudo -n "$WL_BIN" up 2>/dev/null || echo "gpu: 지금은 올리지 못했다(관문이 서버 기동 시 다시 시도)" >&2
else
  echo "gpu: ${RAM_GB:-$(( $(sysctl -n hw.memsize) / 1073741824 ))}GB 호스트 - wired limit 기본값 유지(35B 미적재 티어)"
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
