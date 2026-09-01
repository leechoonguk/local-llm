---
paths:
  - ".claude/rules/**"
  - ".claude/hooks/**"
  - ".claude/settings.json"
  - "Makefile"
---

# 하네스 (규칙 · 훅 · Makefile)

이 레포의 검증 하네스는 `sandbox/.omp/`(omp 용)를 Claude Code 규격으로 옮긴 것이다. 공식 문서: 훅 https://code.claude.com/docs/en/hooks.md, 규칙 https://code.claude.com/docs/en/memory.md. 하네스를 고칠 때는 먼저 공식 문서를 읽는다 — 동작을 추측하지 않는다. 자기 검증은 `make check-harness`.

## 이름 계약 (한 이름, 네 곳)
`.claude/rules/<name>.md` ↔ `.claude/hooks/check-<name>.ts` ↔ Makefile `check-<name>` ↔ `verify` 선행 조건. 하나를 추가하면 넷을 같이 추가한다. 규칙 본문은 `make check-<name>` 을 적는다.

## 규칙 파일
- **절차 절(How-to)은 검증된 구조로 쓴다**(2026-09-01 실측 — 벤치 TO→초록 전환의 원인): 순서 있는 단계 + 단계마다 자기 검증 + 선택은 성질로(이름·습관 금지) + 생성물 즉시 적용 + 과제 힌트 금지. 산출물 목록만 나열하는 절차 절을 만들지 않는다.

- 프런트매터 `paths:`(글롭 리스트, 비어 있지 않음, 각 글롭이 실재 파일과 매치). Claude Code 는 매치되는 파일을 다룰 때 본문을 로드하고, `post-edit` 훅은 같은 `paths` 로 실행할 검사를 고른다 — 규칙의 paths 가 곧 훅의 트리거다.
- 본문은 H1 + 검사 가능한 문장. 사람에게만 유효한 문맥은 README 로.

## 훅 (`.claude/settings.json`)
- `PreToolUse` `Bash` → `pre-bash.ts`(명령 위치에서 deny: brew services 로 Ollama/oMLX 기동, sudo). 모델 다운로드(ollama pull·hf download·install.sh) deny 는 2026-08-25 제거(사용자 허용). git commit/push ask 게이트는 2026-08-27 제거(승인 부담 — omp 하네스의 strict-no-vcs-publish deny 만 유지). 문자열·heredoc 안의 같은 단어는 막지 않는다.
- `PreToolUse` `Edit|Write` → `pre-write.ts`(레이아웃: bench/ 플랫·파일명, hooks/ 는 .ts, rules/ 는 .md, sandbox/.omp 편집 금지).
- `PostToolUse` `Edit|Write` → `post-edit.ts`(paths 매치 검사 실행 → 위반이면 exit 2 + stderr, 없으면 라이브 반영 알림).
- 명령은 `node "$CLAUDE_PROJECT_DIR"/.claude/hooks/<file>.ts`, `timeout` 명시. `hooks/` 는 TypeScript 만(node 24+ 가 직접 실행, 의존성 없음). 블록 주석 안에 `*/` 가 들어가는 글롭(`pre-*/post-*`)을 쓰지 않는다 — 주석이 닫혀 파싱이 깨진다.
- 훅 본체는 `guarded()` 로 감싼다 — 훅의 예외는 exit 0 으로 삼켜 도구 호출을 죽이지 않되 stderr 에 남긴다.
- 검사는 순수 파일 읽기다. 서버·네트워크를 만지지 않는다(편집 지연 = 검사 시간). 예외는 `check-live-sync`(호스트의 라이브 설정 파일 + 루프백 2s)와 `check-autostart`(brew services·launchctl·로그인 항목 조회) — 미설치 시스템은 skip 으로 처리해 다른 호스트의 verify 를 깨지 않는다.

## 검사 전수 점검

절차와 지금까지의 결과는 `.claude/rules/sandbox-harness-review.md` 에 있다 — 그 규칙이 관점의 경계도
함께 정한다: **피험자 트리의 규칙은 그 프로젝트의 표준만 담고, 측정·판정은 이 워크스페이스에 남긴다.**
`make check-sandbox-harness-review` 가 그 경계를 검사한다.

## Makefile
- 모든 타깃은 `.PHONY` 등재 + `## 설명`. `check-<name>` 레시피는 `node .claude/hooks/check-<name>.ts` 한 줄. `verify` 는 모든 `check-*` 를 선행 조건으로 가진다 — verify 에 없는 검사는 아무도 안 도는 주장이다.
