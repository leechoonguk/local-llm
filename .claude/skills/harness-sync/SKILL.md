---
name: harness-sync
description: sandbox/ 하네스·피험자 코드를 ~/Workspace/fast-api-standard 와 양방향 싱크한다. fas 에 새 구현이 쌓였을 때, 하네스 표준이 갈라졌을 때, check-harness-sync 가 빨간불일 때 쓴다. 결과는 make check-harness-sync 가 기계로 판정한다.
---

# harness-sync — fast-api-standard ↔ sandbox 양방향 싱크

종착 상태는 하나다: **벤치 과제 도려내기와 의도 분기 원장(`sandbox/SANDBOX.md`)에 적힌 항목만 빼고
두 트리는 동일하다.** 판정은 `make check-harness-sync` — 이 스킬의 모든 단계는 그 검사를 초록으로
만드는 과정이고, 원장에 없는 diff 는 싱크 부채다.

## 0. 전제

- 벤치 셀 부재(`make preflight` 의 pgrep 확인), 양쪽 트리 커밋 클린.
- fas 는 사용자의 실사용 레포다 — 커밋은 하되 push 는 사용자 몫.

## 1. 전수 diff 와 분류

```bash
make check-harness-sync           # 현재 부채 목록이 곧 작업 목록이다
```

diff 하나마다 셋 중 하나로 분류한다:
- **수렴**: 한쪽의 진화를 다른 쪽으로. 방향 판정 기준 —
  실측 근거가 붙은 쪽이 이긴다 · "Measure The Domain"(이름 하드코딩 제거) 리팩토링이 이긴다 ·
  더 넓은 채널/경로 커버리지(eval, edit 패치 헤더, MV)가 이긴다 · 죽은 코드(소비자 0)는 지는 쪽이 아니라 삭제 대상이다.
- **원장 등재**: 진짜 트리별이면 `SANDBOX.md` 원장에 행을 **같은 변경에서** 추가하고,
  `check-harness-sync` 의 허용 목록에도 사유와 함께 추가한다(둘은 짝이다 — 검사가 원장 언급을 강제한다).
- **버그**: 어느 쪽에도 옳지 않으면 양쪽 다 고친다.

## 2. 순서 (측정된 의존 방향)

1. **메타 층 먼저** — 룰·훅을 만드는 룰·훅(`omp-conventions`·`omp-hooks`·`check-omp-*`).
   메타를 먼저 맞추면 이후 이식이 상대 트리에서 즉시 검증된다(실측: 이식된 검사가 fas 규칙
   부패 30건·정책 가드 eval 우회를 그 자리에서 잡았다).
2. lib → post 검사 → pre 가드 → 규칙 문서 → 스킬 → AST 규칙(+테스트 케이스 필수).
3. **피험자 소스** — 통째 이식 시 rsync 는 `--delete` 없이, 대체분은 명시 삭제(리비전 중복 검증).
   포트·compose 프로젝트명·env 값은 sandbox 대역(1xxxx)을 보존한다.
4. 인프라 — env-간접화 구조는 공유, 값만 트리별.

## 3. 가드 이식의 계약

- sandbox 가드 변경은 프루프(`.claude/skills/llm-bench/proofs/`)가 초록이어야 한다 —
  프루프는 fas 팩토링의 실구멍(M2/M3: edit 의 `input.path` 미독)을 잡은 전적이 있다.
- 정책 가드는 교차 이식 금지: `strict-no-vcs-publish`(sandbox) ↔
  `strict-verified-git`+`strict-publish-consent`(fas). 기계 가드만 합친다.
- TTSR 규칙을 옮기면 fires-on 표본과 함께 옮기고, 양 트리에서 `check-omp-rules` 의
  엔진 검증(omp ttsr test)이 돌게 한다.

## 4. 벤치 과제 정합 (소스 싱크 후 필수)

1. `make check-bench-tasks` — 정답이 기준선에 편입됐으면 여기서 울린다. 울리면 과제를
   재도려낸다: 새 정답을 `reference/answers/` 로, 매니페스트·브리핑·러너 프롬프트를
   한 사슬로(프롬프트가 옛 정답을 말하는 드리프트가 실측 1회 있었다 — 셋을 같이 본다).
2. **새 과제 제안 — 자동 등록 금지, 반드시 사용자에게 제안한다.** 이번 싱크로 새로 들어온
   fas 구현을 훑고(`git -C ~/Workspace/fast-api-standard log --oneline <이전 싱크>..`),
   벤치 후보 조건에 맞는 것을 표로 제시한다:
   - greenfield 성립: 도려냈을 때 기준선이 초록이고, 정답 마이그레이션이 체인 꼬리라
     피험자의 migrate-gen 번호가 매니페스트와 맞는다
   - 대표성: 실제로 원해서 만든 기능(레포에 형제 패턴이 있는 것이 좋다)
   - 채점 가능: 산출물이 매니페스트로 세어지고 게이트가 문다
   사용자가 고르면 `bench-tasks.md` 의 "새 과제를 추가할 때" 절차로 등록한다.

## 5. 마감

- 양 트리 덱 재빌드, 세 게이트 초록: `cd sandbox && make verify` ·
  `cd ~/Workspace/fast-api-standard && make verify` · 루트 `make verify`(check-harness-sync 포함).
- 상속 마이그레이션의 스타일 지적은 푸시 면제 설계다(pushed 리비전은 불변) —
  local-llm push 로 역사화된다.
- 커밋은 양쪽 각각, 본문에 방향 판정 근거를 남긴다. fas push 는 사용자에게 맡긴다.
