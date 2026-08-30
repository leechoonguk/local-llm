---
paths:
  - ".claude/skills/llm-bench/runner.ts"
  - ".claude/skills/llm-bench/tasks/**"
  - ".claude/skills/llm-bench/reference/**"
---

# 벤치 과제의 모양과 이름

과제를 새로 만들거나 고칠 때 지키는 계약 — `make check-bench-tasks` 가 넷을 기계로 확인한다.

## 1. 모든 과제는 같은 모양이다: 없는 것을 더한다 (`shape: "greenfield"`)

피험자는 **동작하는 저장소에 새 기능을 추가**한다. 시작 시점의 트리는 게이트가 초록이고, 과제가 요구하는
산출물은 하나도 없다. 다른 모양(예: 정답을 지우고 재현시키기)을 도입하지 않는다.

한 번 그렇게 만들어 봤고 두 가지가 무너졌다.

- **채점이 뒤집힌다.** 지운 자리를 `git status` 로 세면 아무것도 안 한 피험자가 만점을 받고, 정답을 정확히
  복원한 피험자가 0점을 받는다. 실제로 `writes: 0` 인 만점 행이 기록에 셋 남았다.
- **지름길이 생긴다.** 정답이 히스토리에 있으므로 `git checkout HEAD -- <경로>` 한 줄이면 과제가 끝난다.
  가드로 막을 수는 있지만, 애초에 지울 것이 없으면 막을 것도 없다.

## 2. 정답은 피험자 트리에 두지 않는다

기대 산출물의 사본이 필요하면 `reference/answers/` 에 둔다. `sandbox/` 안에 있으면 그것은 정답이 아니라
**기준선의 일부**이고, 과제는 성립하지 않는다.

## 3. 과제는 이름으로 부른다

`rest`, `integration` 처럼 **무엇을 만드는지**로 부른다. `mode: "A"|"B"` 같은 글자는 쓰지 않는다 — 그 글자는
과제에 대해 아무것도 말해 주지 않아서, 읽는 사람이 매번 어느 쪽이 무엇인지 다시 확인해야 한다. 기록·러너·
스킬 어디서도 "Mode A/B" 어휘를 쓰지 않는다.

## 4. 기대 산출물 수는 매니페스트와 일치한다

`reference/<ref>.manifest.json` 을 가진 과제는 `expect` 가 `added.length + modified.length` 와 같아야 한다.
어긋나면 채점이 조용히 다른 것을 재게 된다.

## 새 과제를 추가할 때

1. `sandbox/` 가 그 기능 **없이** 초록인지 확인한다(`cd sandbox && make verify`).
2. 브리핑(`tasks/<name>_spec.md`)에 **이름으로 파생되는 식별자**를 명시한다. 산출물 이름이 어떤 문자열에서
   파생된다면 그 문자열은 브리핑에 있어야 한다 — 트리에서 유추하게 두면 과제가 이름 맞히기가 된다.
3. 기대 산출물 목록을 `reference/<ref>.manifest.json` 에 적고 `expect` 를 그 합으로 둔다.
4. `make check-bench-tasks` 와 `make preflight` 로 확인한다.
