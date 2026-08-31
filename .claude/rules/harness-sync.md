---
paths:
  - ".claude/skills/harness-sync/**"
  - ".claude/hooks/check-harness-sync.ts"
---

# 하네스 싱크 (sandbox ↔ fast-api-standard)

두 트리는 **의도 분기 원장(`sandbox/SANDBOX.md`)에 등재된 항목만 빼고 동일**해야 한다 — `make check-harness-sync` 가 세 층위로 판정한다. 절차는 `/harness-sync` 스킬.

## 판정 층위
1. **피험자 코드는 무관용 바이트 동일** — `backend/app`·`backend/tests`·`backend/alembic`·`frontend/src`·`api/*.http`·`backend/Makefile`. 여기의 diff 는 어떤 사유로도 허용되지 않는다.
2. **원장 항목**은 세 부류 — 한쪽 전용(TREE_ONLY: 정책 가드·SANDBOX.md), 값 트리별(VALUE_OK: env·포트·compose 이름·덱 생성물), 정책 어휘 한정 부분 분기(PATTERN_OK: RULES.md 발행 절·no-subagents 사유문). **허용 목록에 넣을 때는 원장에 같은 항목의 행을 함께 넣는다** — 검사가 원장 언급을 강제한다.
3. **루트 Makefile 은 타깃 집합으로** — 차이는 정확히 fas 전용 `{commit, push}` 뿐이어야 한다.

## 한계 (정직하게)
- PATTERN_OK 파일 안에서 허용 어휘를 **포함하는** 줄의 드리프트는 이 검사가 못 본다 — 그 파일들을 고칠 때는 `/harness-sync` 1단계의 분류를 손으로 거친다.
- `check-live-sync` 와 같은 예외 부류다: 프로젝트 밖(`~/Workspace/fast-api-standard`)을 읽고, 짝 트리가 없는 호스트에서는 skip 한다.

## 벤치 과제와의 관계
- 소스 싱크 후 `make check-bench-tasks` 필수 — 정답의 기준선 편입을 잡는다. 재도려낼 때는 정답·매니페스트·브리핑·러너 프롬프트 **넷을 한 사슬로**(프롬프트만 옛 정답을 말하는 드리프트 실측 1회).
- **새 과제 등록은 자동으로 하지 않는다** — 싱크로 새로 들어온 fas 구현 중 후보(greenfield 성립·체인 꼬리·대표성·매니페스트 채점 가능)를 표로 **사용자에게 제안**하고, 선택받은 것만 `bench-tasks.md` 절차로 등록한다.
