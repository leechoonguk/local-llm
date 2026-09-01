---
paths:
  - "ollama/**"
  - "omlx/**"
---

# 자동 시작·자동 재시작 금지 (Ollama · oMLX)

두 서버는 **손으로 띄우고 손으로 내린다.** 로그인 시 자동 시작, 죽었을 때 자동 재시작은 둘 다 꺼 둔다 — 벤치는 "단일 상주 + 명시적 기동 + 로그 `total:` 확인"이 전제이고, 되살아난 서버는 메모리 측정과 세션 비교를 조용히 오염시킨다. 검사: `make check-autostart` (레포 파일 + 이 호스트의 launchd/brew/로그인 항목/oMLX 설정).

## 켜는 방법이 하나뿐이다
| 서버 | 관리 주체 | 기동 | 중지 |
|---|---|---|---|
| Ollama | LaunchAgent `~/Library/LaunchAgents/com.ollama.serve.plist` (← `ollama/com.ollama.serve.plist.template`, `RunAtLoad`/`KeepAlive` false) | `launchctl kickstart -k gui/$(id -u)/com.ollama.serve` | `launchctl kill TERM gui/$(id -u)/com.ollama.serve` |
| oMLX | GUI 앱 `/Applications/oMLX.app`(메뉴바). LaunchAgent 없음 | 앱 메뉴바 Start (※ `omlx start`=brew services=금지) | 앱 메뉴바 Stop |

`ollama/install.sh` 는 bootstrap 뒤 `kickstart` 로 **그 자리에서 한 번** 띄운다. oMLX 앱의 **로그인 시 실행**·crash 자동 재시작은 끈다(로그인 항목으로 검사). 단 `auto_start_on_launch` 는 **true 가 표준**(2026-09-01 반전) — 서버 수명을 앱 수명에 묶는 것이 앱 자식 서버를 보장하는 유일 경로다(셔틀 start/restart 는 고아 서버를 띄운다는 실측). 재기동 정본은 `bash omlx/ensure-app-server.sh --restart`.

## 금지
- `brew services start|restart|run ollama|omlx` — Homebrew plist 는 KeepAlive/RunAtLoad 가 true 다. `pre-bash` 훅이 deny 하고, install.sh 에 있으면 검사가 잡는다. 남아 있는 `homebrew.mxcl.omlx.plist`, 예전 레포 LaunchAgent `com.local-llm.omlx.plist`(앱과 포트 충돌)도 위반.
- oMLX `~/.omlx/settings.json` `server.auto_start_on_launch` 는 `false`(키가 없으면 oMLX 기본값 true → 위반). `omlx/install.sh` 가 쓰고, admin 화면에서 다시 켜면 검사가 잡는다.
- `/Library/LaunchAgents`, `/Library/LaunchDaemons` 의 ollama/omlx 항목, 로그인 항목의 Ollama/oMLX 앱.

## Ollama 가 `disabled` 인 상태
CLAUDE.md 대로 Ollama LaunchAgent 는 `launchctl disable` 로 내려 두었다. disabled 면 plist 의 값과 무관하게 자동 시작이 아니므로 통과한다. 다시 쓸 때는 `launchctl enable` 후 템플릿(둘 다 false)으로 재설치한다.
