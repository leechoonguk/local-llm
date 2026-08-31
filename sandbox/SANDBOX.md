# sandbox — llm-bench 피험자 트리

`~/Workspace/fast-api-standard` 를 벤치에 필요한 코어(**batch·user·integration** 도메인 + auth·health + core 인프라 + `.omp/` 하네스 + frontend)로 줄인 사본이다. 로컬 모델이 `skill://llm-bench`(`.claude/skills/llm-bench/`) 과제를 수행하는 공간이며, 하네스가 그대로라 `make verify` 가 원본과 같은 기준으로 채점한다.

## 원본과 다른 점

| 항목 | 원본 | sandbox |
|---|---|---|
| git | 자체 저장소 | **git 저장소 아님.** local-llm 이 파일을 추적하고, 원복은 부모 저장소의 `git checkout -- sandbox && git clean -fdq sandbox`. 임시 git 을 만들지 않는다 |
| 마이그레이션 | 73개(item/todo/task 생성·삭제, integration replace 반복 등 역사 누적) | churn 제거 + 하네스 정합(레이아웃·단일 테이블·downgrade·개행) 수정. **git 없이 `make verify` 통과** — 마이그레이션 불변 규칙(`@{upstream}`)이 git 부재 시 전부 "unpushed"로 보고 현행 레이아웃 규칙을 강제하므로, 남는 마이그레이션이 전부 그 규칙을 통과해야 한다 |
| compose 프로젝트 | `fast-api-standard` | `local-llm-sandbox` (볼륨·컨테이너 분리) |
| 호스트 포트 | 8000 / 5173 / 5432 / 6379 / 6006 / 4317 | **18000 / 15173 / 15432 / 16379 / 16006 / 14317** — 원본 스택과 동시에 뜰 수 있다. 컨테이너 내부 주소(`postgres:5432`, `redis:6379`)는 그대로 |
| 포트가 박힌 파일 | — | `docker-compose.yml`, `.env.example`, `backend/.env.example`, `api/.env.example`, `backend/Makefile`, `backend/scripts/start.sh`, `backend/Dockerfile`, `frontend/{Makefile,vite.config.ts,nginx.conf}`, `.omp/hooks/lib/backend-api-http.ts`(`@base` 는 `:18000`), `backend-api-flow.ts`, `.omp/rules/*.md` |
| 벤치 자산 | `.omp/skills/llm-bench`, `bench-llm-runner.ts`, `make bench-llm` | **없음** — 피험자가 자기 채점 절차를 읽으면 안 된다. 규칙 카탈로그·decks 해시도 맞춰 뒀다 |
| `docs/` | 있음 | 제거 |

## 벤치 과제 두 가지 (`.claude/skills/llm-bench/runner.ts` 의 `TASKS`)

- **integration**(Mode A) — 외부 API I2570 을 형제 `search-food-raw-material` 을 본떠 추가. 러너가 부모 상태 복원(레퍼런스 산출물 삭제 + 역패치)으로 정답을 숨긴다.
- **rest**(Mode B) — `notice` CRUD 를 형제 `batch` 를 본떠 신규 작성. 정답이 레포에 없어 누출 0.

## 설치 (새 기계)

```bash
cd sandbox
cp .env.example .env && cp backend/.env.example backend/.env && cp api/.env.example api/.env
(cd backend && uv sync)
(cd frontend && npm install)
(cd decks && make build)          # 훅/규칙 해시 동기화 — 하네스를 건드리면 다시
make db-init && make verify       # git 없이 exit 0 이어야 벤치 baseline
```
`.env` 3개, `backend/.venv`, `frontend/node_modules`, `decks/*.html` 은 sandbox 안의 `.gitignore` 로 제외된다. **이 `SANDBOX.md` 를 포함해 sandbox 새 파일은 부모 저장소에 `git add` 해 둔다** — 러너의 `git clean` 이 untracked 를 지우기 때문이다.

## 원본 동기화

의도적으로 자동화하지 않는다. fast-api-standard 가 바뀌면 `git -C ~/Workspace/fast-api-standard archive <rev> | tar -x -C sandbox` 후 위 표의 포트 치환·벤치 자산 제거·마이그레이션 정리를 다시 한다(`.claude/skills/llm-bench/` 의 절차). 반대로 sandbox 에서 실측으로 잡은 하네스 구멍은 원본으로 보내는 후보다.

## fast-api-standard 와의 의도 분기 원장 (2026-09-01 전면 싱크 후)

이 트리는 `~/Workspace/fast-api-standard` 와 **하네스·피험자 코드가 동일**하다. 남는 차이는 전부 의도된 것이고, 아래가 전량이다 — 여기 없는 diff 가 생기면 싱크 부채다.

| 항목 | fas | sandbox | 사유 |
|---|---|---|---|
| VCS 정책 | `strict-verified-git` + `strict-publish-consent`(+lib), `make commit/push`, RULES.md 발행 절 | `strict-no-vcs-publish`, RULES.md 금지 절 | 실사용은 검증된 발행, 벤치 피험자는 VCS 전면 금지 |
| `strict-no-subagents` 사유문 | 일반론 | 로컬 모델 한 슬롯(GPU 공유) | 정책은 같고 근거가 트리별 |
| 포트 대역 | 2xxxx (`.env`·`api/.env`·`launch.json`) | 1xxxx | 동시 기동 가능해야 한다 |
| compose 프로젝트명 | `fast-api-standard` | `local-llm-sandbox` | 볼륨 분리 |
| `SANDBOX.md` | 없음 | 이 파일 | 벤치 트리 설명 |
| `hook-publish-consent.ts` | 있음(lib) | 없음 | fas 발행 동의 가드의 전용 lib |
| `decks/package-lock.json` | 없음 | 있음 | 덱 빌드 로컬 산물 |
| 벤치 과제 도려내기 | — | `search-barcode-linked-product` 산출물 부재(정답은 `.claude/skills/llm-bench/reference/answers/`) | 과제 성립 조건 — 현재 양쪽 다 부재라 코드 diff 는 없음 |
| `decks/*/slides.md` | 각자 재생성 | 각자 재생성 | sync 해시·정책 가드 목록이 트리별 |
