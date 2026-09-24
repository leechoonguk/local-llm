---
paths:
  - "ollama/**"
  - "omlx/**"
  - "omp/**"
---

# 라이브 반영 (레포 설정 ↔ 이 호스트)

레포의 `ollama/`, `omlx/`, `omp/` 는 설정의 단일 진실이지만, 실제로 도는 것은 `~/.omp/agent/`, `~/.omlx/`, Ollama 모델 저장소다. 레포만 고치고 라이브를 안 맞추면 벤치가 옛 설정을 잰다. 그래서 편집 뒤 `post-edit` 훅이 이 검사를 돌려 어긋난 곳과 맞추는 명령을 돌려준다 — `make check-live-sync`. **편집 직후 어긋남은 당연하다**: 아래 반영 절차를 하고 다시 돌린다. 자동으로 복사하지 않는다(config.yml 은 omp 자신의 상태가 섞여 있고, oMLX 는 재시작이 필요하다).

## 대응표
| 레포 | 라이브 | 반영 |
|---|---|---|
| `omp/models.yml` | `$(omp config path)/models.yml` (기본 `~/.omp/agent`) | `cp` — 바이트 동일. 다른 provider 가 있으면 `providers` 아래로 병합 |
| `omp/config.fragment.yml` | 같은 곳 `config.yml` | `modelRoles.default/tiny`, `defaultThinkingLevel` 줄만 손으로 |
| `omlx/model_settings.json`, `model_profiles.json` | `~/.omlx/` | `cp` 후 `omlx restart`(메뉴바 앱이 서버 관리), 로그 `total:` 로 단일 상주 확인 |
| `omlx/install.sh` 의 settings 값 | `~/.omlx/settings.json` `server.port`, `memory.memory_guard_tier`, `cache.hot_cache_max_size` | `omlx/install.sh` 의 python 블록 |
| `omlx/model_settings.json` 의 모델·드래프터 | oMLX 앱 스토어 `~/.omlx/models/mlx-community/<name>` (HF 캐시는 2026-08-28 폐지) | 앱 다운로드 또는 `POST /admin/api/hf/download` — 절차는 `/add-model` |
| (oMLX 서버) | `/Applications/oMLX.app` | 사용자가 DMG 설치. brew 서비스·예전 LaunchAgent 는 `omlx/install.sh` 가 걷어낸다 |
| `omlx/wired-limit.sh` | `/usr/local/sbin/omlx-wired-limit`(root 소유 사본, 내용 동일) + `/etc/sudoers.d/omlx-wired-limit`(NOPASSWD, 그 경로만) | `omlx/install.sh`(sudo 1회, 사용자). 값 자체는 영구화하지 않는다 — 관문 `ensure-app-server.sh` 가 기동 시 `up`. 검사는 사본 동일성 + "서버 가동 중 `iogpu.wired_limit_mb` == 티어"(sudoers 는 root 전용이라 읽지 않는다) |
| `ollama/com.ollama.serve.plist.template` | `~/Library/LaunchAgents/com.ollama.serve.plist` (자리표시자 치환됨) | 사용자가 `ollama/install.sh` |
| `ollama/Modelfile.<name>` | `ollama show <name>` 의 parameters | `ollama create <name> -f ollama/Modelfile.<name>` — 서버(127.0.0.1:11434)가 떠 있을 때만 비교, 내려가 있으면 skip |

## 검사 원칙
- 설치돼 있지 않은 시스템(omp 없음, `~/.omlx` 없음, plist 없음)은 이슈가 아니라 **skip** 이다 — 다른 호스트에서도 `make verify` 가 깨지지 않는다.
- 호스트 접근은 파일 읽기 + `omp config path` + 루프백 `curl --max-time 2` 뿐이다. 이 검사만 예외적으로 호스트 상태를 읽는다(`harness.md`).
- 라이브를 맞춘 뒤 **`make smoke`**(서빙·응답·reasoning 분리·MTP 발화·서버가 되읽어 준 설정값)까지가 반영 완료다. 한 번에 하려면 `make bake` — 절차와 진단은 `/bake-config`.
- 재시작 성공 여부는 앱 셔틀 메시지가 아니라 **uptime**(`lsof -nP -iTCP:9090 -sTCP:LISTEN -t | xargs ps -o etime=`)으로 판정한다 — 셔틀은 성공해도 실패 문구를 뱉는다(실측).
