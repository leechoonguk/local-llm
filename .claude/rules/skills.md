---
paths:
  - ".claude/skills/**"
---

# 스킬 (.claude/skills/<name>/SKILL.md)

공식 규격(https://code.claude.com/docs/en/skills.md): 프런트매터 `name`(생략 시 디렉터리명), `description`(모델이 언제 쓸지 판단하는 근거; `when_to_use` 와 합쳐 1536자에서 잘린다), `allowed-tools`, `paths`, `context: fork` 등. 이 레포의 추가 계약 — `make check-skills`:

- 디렉터리마다 `SKILL.md`. `name` 은 디렉터리명과 같게 명시한다(목록에서 이름이 다르면 `/이름` 호출과 어긋난다).
- `description` 은 비어 있지 않고, "언제 쓰는지"를 한국어로 적는다. 1536자 이하.
- CLAUDE.md "## 디렉터리" 절이 스킬 이름을 등재한다 — 스킬을 추가하면 그 줄도 고친다.
- 스킬 본문은 절차만 담는다. 결과 기록 표준은 `bench/README.md`, 모델 사실은 README.md 를 가리키고 복제하지 않는다.
- 세 스킬의 역할: `bench-model`(1단계 단발), `llm-bench`(2단계 장기 세션, `sandbox/`), `add-model`(5곳 동시 수정). 기본 코더 교체는 2단계 통과가 필요조건이다.
