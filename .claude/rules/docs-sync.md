---
paths:
  - "CLAUDE.md"
  - "README.md"
  - "ollama/**"
  - "omlx/**"
  - "omp/**"
  - "Makefile"
---

# 문서 ↔ 설정 동기화 (CLAUDE.md · README.md)

README.md 는 사람용 문서이자 실측 기록, CLAUDE.md 는 작업 규칙과 환경 사실이다. 설정이 바뀌면 문서의 사실 문장도 바뀌어야 한다 — `make check-docs-sync`.

- CLAUDE.md 의 ``기본 코더: `X` `` 는 `omp/config.fragment.yml` `modelRoles.default` 와, ``보조: `Y` `` 는 `modelRoles.tiny` 와 같다.
- CLAUDE.md 가 `README "제목"` 으로 인용하는 절은 README.md 에 그 제목을 포함한 `##`~`####` 제목으로 실재한다. README 절 제목을 바꾸면 CLAUDE.md 인용도 바꾼다.
- README "## 파일" 블록은 `ollama/`, `omlx/`, `omp/` 의 모든 파일과 하네스 경로(`Makefile`, `.claude/rules/`, `.claude/hooks/`)를 적는다. 파일을 추가·삭제하면 이 블록도 고친다.
- README 는 `make verify` 를 검증 진입점으로 언급한다.
- 실측 숫자(메모리, tok/s, 중단 토큰 수)는 README 해당 표에 날짜와 함께. 추정치는 "추정". 개발사 벤치는 "자체 측정".
- 주석·README 는 한국어("~한다" 체), 코드 식별자·커밋 메시지는 영어.
